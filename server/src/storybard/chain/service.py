from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import TypeAdapter

from storybard.chain.graph import ChainRuntime
from storybard.chain.ops import CreateMemoryOut, WorldOp, WorldUpdateOut, apply_op
from storybard.chain.prompts import (
    intent_prompt,
    mechanical_check_prompt,
    memory_regression_prompt,
    narrator_prompt,
    opportunity_spotting_prompt,
    plan_synthesis_prompt,
    plausibility_prompt,
    thread_tick_prompt,
    tone_assessment_prompt,
    world_update_prompt,
)
from storybard.domain.campaign import Campaign
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.memory import Memory
from storybard.services.duration import parse_duration
from storybard.services.llm.schemas import (
    IntentOut,
    MechanicalCheckOut,
    NarratorOut,
    OpportunitySpottingOut,
    PlanSynthesisOut,
    PlausibilityOut,
    ThreadTickOut,
    ToneAssessmentOut,
)

NODE_OUTPUT_MODELS: dict[str, type] = {
    "intent_parse": IntentOut,
    "plausibility_check": PlausibilityOut,
    "thread_tick": ThreadTickOut,
    "opportunity_spotting": OpportunitySpottingOut,
    "mechanical_check": MechanicalCheckOut,
    "tone_assessment": ToneAssessmentOut,
    "plan_synthesis": PlanSynthesisOut,
    "world_update": WorldUpdateOut,
    "narrator": NarratorOut,
    "memory_regression": CreateMemoryOut,
}

# node_type -> prompt builder + the state keys it reads, for the "retry" path (regenerates
# a single step without touching graph position; see chain/service.py docstring below).
_RETRY_PROMPT_BUILDERS = {
    "intent_parse": lambda s: intent_prompt(
        player_text=s["player_text"], mode=s.get("mode", "explore"), recent_turns=s.get("recent_turns", [])
    ),
    "plausibility_check": lambda s: plausibility_prompt(
        player_text=s["player_text"],
        intent=s["intent"],
        scene_text=s.get("scene_text", ""),
        actor_context=s.get("actor_context", {}),
        campaign_summary=s.get("campaign_summary", ""),
        recent_turns=s.get("recent_turns", []),
    ),
    "thread_tick": lambda s: thread_tick_prompt(
        player_text=s["player_text"],
        active_clocks=s.get("active_clocks", []),
        recent_turns=s.get("recent_turns", []),
    ),
    "opportunity_spotting": lambda s: opportunity_spotting_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        active_threads=s.get("active_threads", []),
        scene_text=s.get("scene_text", ""),
        actor_context=s.get("actor_context", {}),
        recent_turns=s.get("recent_turns", []),
    ),
    "mechanical_check": lambda s: mechanical_check_prompt(
        player_text=s["player_text"], plausibility=s["plausibility"], turn_count=s.get("turn_count", 0)
    ),
    "tone_assessment": lambda s: tone_assessment_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        previous_tone=s.get("previous_tone", {}),
        recent_turns=s.get("recent_turns", []),
    ),
    "plan_synthesis": lambda s: plan_synthesis_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        thread_tick=s.get("thread_tick", {}),
        opportunity_spotting=s.get("opportunity_spotting", {}),
        tone=s.get("tone", {}),
        campaign_summary=s.get("campaign_summary", ""),
        recent_turns=s.get("recent_turns", []),
        turns_since_thread_activity=s.get("turns_since_thread_activity", 0),
        turn_count=s.get("turn_count", 0),
    ),
    "world_update": lambda s: world_update_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        active_threads=s.get("active_threads", []),
        thread_tick_suggestions=s.get("thread_tick", {}).get("tick_suggestions", []),
        hook_ideas=s.get("opportunity_spotting", {}).get("hook_ideas", []),
        known_actors=s.get("known_actors", []),
        known_locations=s.get("known_locations", []),
        narration=s.get("narration", ""),
        recent_turns=s.get("recent_turns", []),
    ),
    "narrator": lambda s: narrator_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        plan=s.get("plan", {}).get("plan", ""),
        tone=s.get("tone", {}),
        style_description=s.get("style_description", ""),
        verbosity_words=s.get("verbosity_words", 150.0),
        scene_text=s.get("scene_text", ""),
        actor_context=s.get("actor_context", {}),
        recent_turns=s.get("recent_turns", []),
        relevant_memories=s.get("relevant_memories", []),
        known_actors=s.get("known_actors", []),
        known_locations=s.get("known_locations", []),
        recent_world_events=s.get("recent_world_events", []),
        campaign_summary=s.get("campaign_summary", ""),
    ),
    "memory_regression": lambda s: memory_regression_prompt(
        player_text=s["player_text"],
        narration=s.get("narration", ""),
        previous_summary=s.get("campaign_summary", ""),
    ),
}


def _clean_state(values: dict) -> dict:
    return {k: v for k, v in values.items() if not k.startswith("_proposed_")}


async def apply_world_update_ops(db: AsyncSession, *, campaign_id: uuid.UUID, resolved: dict) -> dict:
    """Applies each op in the approved/edited World Update batch via apply_op(), which
    enforces every cap/gate deterministically (never trusted to the LLM). Every op's
    outcome — including rejections — is attached back onto `resolved` so it's visible in
    the ChainStep trace, never a silent no-op.
    """
    applied_results = []
    for raw_op in resolved.get("ops", []):
        op = TypeAdapter(WorldOp).validate_python(raw_op)
        result = await apply_op(db, campaign_id=campaign_id, op=op)
        applied_results.append(
            {
                "op": raw_op.get("op"),
                "applied": result.applied,
                "reason": result.reason,
                "entity_id": str(result.entity_id) if result.entity_id else None,
            }
        )
    return {**resolved, "applied_results": applied_results}


async def _apply_tone_assessment(db: AsyncSession, *, campaign_id: uuid.UUID, resolved: dict) -> None:
    """Direct write — Tone Assessment is simple enough it doesn't need the ops vocabulary,
    and nothing else needs to gate it (spec.md: tone only ever affects prose)."""
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if campaign:
        campaign.tone_state = resolved
        await db.flush()


async def _apply_plausibility_time(db: AsyncSession, *, campaign_id: uuid.UUID, resolved: dict) -> None:
    """Direct write — advances Campaign.current_datetime by the duration Plausibility
    Check's free-text `time_passed` parses to (best-effort; unparseable text advances zero,
    it never fails the turn). Bookkeeping, not narrative canon, so no ops vocabulary needed.
    See spec.md "What a tick actually is, now."
    """
    delta = parse_duration(resolved.get("time_passed"))
    if delta.total_seconds() == 0:
        return
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if campaign:
        campaign.current_datetime = campaign.current_datetime + delta
        await db.flush()


async def _apply_memory_regression(
    db: AsyncSession, *, campaign_id: uuid.UUID, owner_actor_id: uuid.UUID, resolved: dict
) -> None:
    """Direct write — deliberately separate from the Thread-focused ops vocabulary. Memory
    is low-stakes personal recollection, not persistent shared world state, so no caps.
    Also rewrites Campaign.summary (the rolling "story so far") every turn — reusing this
    node since it's the one that already runs last and already sees the full narration,
    rather than adding a dedicated chain node just for the summary."""
    for entry in resolved.get("memories", []):
        db.add(
            Memory(
                campaign_id=campaign_id,
                owner_actor_id=owner_actor_id,
                title=entry.get("title"),
                text=entry["text"],
                importance=entry.get("importance", 1),
            )
        )
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if campaign and resolved.get("campaign_summary_update"):
        campaign.summary = resolved["campaign_summary_update"]
    await db.flush()


async def advance_turn(
    *, runtime: ChainRuntime, db: AsyncSession, turn_run: TurnRun, resume_or_initial: Any
) -> dict:
    """Runs the graph until it next pauses on interrupt() or completes.

    `resume_or_initial` is either the initial ChainState dict (a fresh turn) or a
    Command(resume=...) (continuing a paused one). Persists a ChainStep on every pause,
    and finalizes the TurnRun on completion. Returns a small dict describing what happened
    (used to build the API response and the WebSocket broadcast payload).
    """
    config = {"configurable": {"thread_id": str(turn_run.id)}}

    await runtime.graph.ainvoke(resume_or_initial, config)
    snapshot = await runtime.graph.aget_state(config)

    if snapshot.next:
        task = snapshot.tasks[0]
        interrupt_value = task.interrupts[0].value
        node_type = interrupt_value["node_type"]
        proposed = interrupt_value["proposed"]

        existing = (
            await db.execute(select(ChainStep).where(ChainStep.turn_run_id == turn_run.id))
        ).scalars().all()

        step = ChainStep(
            turn_run_id=turn_run.id,
            node_type=node_type,
            sequence=len(existing),
            input_snapshot=_clean_state(snapshot.values),
            raw_output=proposed,
            status="pending",
        )
        db.add(step)
        turn_run.status = "paused"
        await db.flush()

        return {"status": "paused", "step": step}

    turn_run.status = "completed"
    turn_run.final_narration = snapshot.values.get("narration")
    turn_run.completed_at = datetime.now(timezone.utc)

    campaign = (
        await db.execute(select(Campaign).where(Campaign.id == turn_run.campaign_id))
    ).scalar_one_or_none()
    if campaign:
        campaign.turn_count += 1

    await db.flush()
    return {"status": "completed", "turn_run": turn_run}


async def resolve_step(
    *,
    runtime: ChainRuntime,
    db: AsyncSession,
    step: ChainStep,
    turn_run: TurnRun,
    action: str,
    edited_output: dict | None,
) -> dict:
    """Approve/edit a pending ChainStep and resume the graph. `retry` regenerates the same
    step in place (a fresh LLM call against the same inputs) without advancing the graph —
    it doesn't need LangGraph's resume mechanism at all, just re-runs the node's own prompt
    builder directly against the step's recorded input_snapshot.
    """
    output_model = NODE_OUTPUT_MODELS[step.node_type]

    if action == "retry":
        system, user = _RETRY_PROMPT_BUILDERS[step.node_type](step.input_snapshot)
        out = await runtime.llm.structured_chat(
            model=runtime.model, system=system, user=user, output_model=output_model
        )
        step.raw_output = out.model_dump()
        await db.flush()
        return {"status": "paused", "step": step}

    if action == "edit":
        resolved = output_model.model_validate(edited_output).model_dump()
        step.final_output = resolved
        step.status = "edited"
    else:  # approve
        resolved = step.raw_output
        step.final_output = resolved
        step.status = "approved"

    if step.node_type == "world_update":
        resolved = await apply_world_update_ops(db, campaign_id=turn_run.campaign_id, resolved=resolved)
        step.final_output = resolved
    elif step.node_type == "plausibility_check":
        await _apply_plausibility_time(db, campaign_id=turn_run.campaign_id, resolved=resolved)
    elif step.node_type == "tone_assessment":
        await _apply_tone_assessment(db, campaign_id=turn_run.campaign_id, resolved=resolved)
    elif step.node_type == "memory_regression":
        await _apply_memory_regression(
            db, campaign_id=turn_run.campaign_id, owner_actor_id=turn_run.actor_id, resolved=resolved
        )

    step.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return await advance_turn(
        runtime=runtime, db=db, turn_run=turn_run, resume_or_initial=Command(resume=resolved)
    )
