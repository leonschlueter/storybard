from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import TypeAdapter

from storybard.chain.graph import CREATIVE_NODE_TYPES, ChainRuntime
from storybard.chain.ops import CreateMemoryOut, ProposeHookOp, WorldOp, WorldUpdateOut, apply_op
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
    twist_prompt,
    world_update_prompt,
)
from storybard.core.config import settings
from storybard.domain.actor import Actor
from storybard.domain.campaign import Campaign
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.memory import Memory
from storybard.services.context_assembly import THREAD_ACTIVITY_OPS
from storybard.services.duration import parse_duration
from storybard.services.oracle import ORACLE_EVENTS
from storybard.services.llm.lmstudio_client import LMStudioClient, LMStudioError
from storybard.services.llm.schemas import (
    IntentOut,
    MechanicalCheckOut,
    NarratorOut,
    OpportunitySpottingOut,
    PlanSynthesisOut,
    PlausibilityOut,
    RollResolutionOut,
    ThreadTickOut,
    ToneAssessmentOut,
    TwistOut,
)
from storybard.services.mechanics.dice import resolve_check

NODE_OUTPUT_MODELS: dict[str, type] = {
    "intent_parse": IntentOut,
    "plausibility_check": PlausibilityOut,
    "thread_tick": ThreadTickOut,
    "opportunity_spotting": OpportunitySpottingOut,
    "mechanical_check": MechanicalCheckOut,
    "roll_resolution": RollResolutionOut,
    "tone_assessment": ToneAssessmentOut,
    "plan_synthesis": PlanSynthesisOut,
    "twist": TwistOut,
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
        scene=s.get("scene"),
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
        scene=s.get("scene"),
    ),
    "mechanical_check": lambda s: mechanical_check_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        turn_count=s.get("turn_count", 0),
        intent=s.get("intent", {}),
        degrees_of_success=s.get("campaign_settings", {}).get("mechanical_degrees_of_success", True),
    ),
    "tone_assessment": lambda s: tone_assessment_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        previous_tone=s.get("previous_tone", {}),
        recent_turns=s.get("recent_turns", []),
        roll_resolution=s.get("roll_resolution"),
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
        roll_resolution=s.get("roll_resolution"),
        active_threads=s.get("active_threads", []),
        scene=s.get("scene"),
        actor_context=s.get("actor_context", {}),
    ),
    "twist": lambda s: twist_prompt(
        player_text=s["player_text"],
        plan=(s.get("plan") or {}).get("plan", "") if isinstance(s.get("plan"), dict) else s.get("plan", ""),
        campaign_summary=s.get("campaign_summary", ""),
        recent_turns=s.get("recent_turns", []),
        active_threads=s.get("active_threads", []),
        actor_context=s.get("actor_context", {}),
        scene=s.get("scene"),
    ),
    "world_update": lambda s: world_update_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        active_threads=s.get("active_threads", []),
        active_clocks=s.get("active_clocks", []),
        thread_tick_suggestions=s.get("thread_tick", {}).get("tick_suggestions", []),
        hook_ideas=s.get("opportunity_spotting", {}).get("hook_ideas", []),
        known_actors=s.get("known_actors", []),
        known_locations=s.get("known_locations", []),
        narration=s.get("narration", ""),
        recent_turns=s.get("recent_turns", []),
        roll_resolution=s.get("roll_resolution"),
        acting_actor_id=s.get("acting_actor_id"),
        scene=s.get("scene"),
    ),
    "narrator": lambda s: narrator_prompt(
        player_text=s["player_text"],
        plausibility=s["plausibility"],
        mechanical_check=s["mechanical_check"],
        plan=(s.get("plan") or {}).get("plan", ""),
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
        npc_impressions=s.get("npc_impressions", []),
        mechanical_texture=s.get("campaign_settings", {}).get("mechanical_degrees_of_success", True),
        twist=(s.get("twist") or {}).get("complication"),
        roll_resolution=s.get("roll_resolution"),
        active_threads=s.get("active_threads", []),
        scene=s.get("scene"),
    ),
    "memory_regression": lambda s: memory_regression_prompt(
        player_text=s["player_text"],
        narration=s.get("narration", ""),
        previous_summary=s.get("campaign_summary", ""),
        known_actors=s.get("known_actors", []),
        track_npc_impressions=s.get("campaign_settings", {}).get("narration_npc_memory", True),
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


async def _embed_or_none(llm: LMStudioClient, text: str) -> list[float] | None:
    """Best-effort: an embedding-server hiccup should degrade the one memory to
    unembedded (sorts last in build_relevant_memories, never crashes the turn), not fail
    the whole memory-regression write."""
    try:
        return await llm.embed(model=settings.LM_STUDIO_EMBED_MODEL, text=text)
    except LMStudioError:
        return None


async def _apply_memory_regression(
    db: AsyncSession, *, campaign_id: uuid.UUID, owner_actor_id: uuid.UUID, resolved: dict, llm: LMStudioClient
) -> None:
    """Direct write — deliberately separate from the Thread-focused ops vocabulary. Memory
    is low-stakes personal recollection, not persistent shared world state, so no caps.
    Also rewrites Campaign.summary (the rolling "story so far") every turn — reusing this
    node since it's the one that already runs last and already sees the full narration,
    rather than adding a dedicated chain node just for the summary.

    Embeds each memory's text on write so build_relevant_memories can do real semantic
    retrieval later instead of a blind importance/recency sort — see that function's
    docstring."""
    for entry in resolved.get("memories", []):
        db.add(
            Memory(
                campaign_id=campaign_id,
                owner_actor_id=owner_actor_id,
                title=entry.get("title"),
                text=entry["text"],
                importance=entry.get("importance", 1),
                embedding=await _embed_or_none(llm, entry["text"]),
            )
        )

    # NPC impressions of the player (feature #19) — the same "never trust the LLM, enforce
    # in code" gate as every other actor-id-bearing op: npc_actor_id must resolve to a
    # real, campaign-scoped Actor or the impression is silently skipped, never written
    # against a fabricated id.
    npc_impressions = resolved.get("npc_impressions", [])
    if npc_impressions:
        npc_ids = {entry["npc_actor_id"] for entry in npc_impressions if entry.get("npc_actor_id")}
        valid_ids: set[str] = set()
        for raw_id in npc_ids:
            try:
                parsed = uuid.UUID(raw_id)
            except ValueError:
                continue
            npc = (
                await db.execute(select(Actor).where(Actor.id == parsed, Actor.campaign_id == campaign_id))
            ).scalar_one_or_none()
            if npc is not None:
                valid_ids.add(raw_id)
        for entry in npc_impressions:
            if entry.get("npc_actor_id") in valid_ids:
                db.add(
                    Memory(
                        campaign_id=campaign_id,
                        owner_actor_id=uuid.UUID(entry["npc_actor_id"]),
                        subject_actor_id=owner_actor_id,
                        title=None,
                        text=entry["text"],
                        importance=2,
                    )
                )

    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if campaign and resolved.get("campaign_summary_update"):
        campaign.summary = resolved["campaign_summary_update"]
    await db.flush()


async def _apply_hard_pacing_floor(
    db: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    resolved: dict,
    campaign_settings: dict,
    turns_since_thread_activity: int,
) -> dict:
    """Feature #20/#15's hard pacing floor — the code-enforced guarantee that closes the
    exact gap live testing proved: the LLM sometimes just doesn't act even when everything
    points to it (see chain/graph.py's _CREATIVE_TEMPERATURE comment — that was one fix;
    this is the deterministic backstop, not a replacement for it). Runs after World
    Update's own ops are already applied: if the scene has been idling past the
    (configurable) threshold and World Update itself proposed nothing thread-related this
    turn, deterministically append and apply one propose_hook seeded from the oracle table
    — never left to the LLM's discretion, the same "never trust the LLM, enforce in code"
    principle every cap in chain/ops.py already follows. threshold <= 0 disables this.
    """
    threshold = campaign_settings.get("narration_hard_stagnation_threshold", 5)
    if threshold <= 0 or turns_since_thread_activity < threshold:
        return resolved

    already_acted = any(
        r.get("applied") and r.get("op") in THREAD_ACTIVITY_OPS for r in resolved.get("applied_results", [])
    )
    if already_acted:
        return resolved

    text = (
        random.choice(ORACLE_EVENTS)
        if campaign_settings.get("narration_oracle_enabled", True)
        else "Something in the world shifts, demanding attention."
    )
    op = ProposeHookOp(op="propose_hook", origin="hard_pacing_floor", proposed_text=text, touches_entity_id=None)
    result = await apply_op(db, campaign_id=campaign_id, op=op)
    resolved.setdefault("applied_results", []).append(
        {
            "op": "propose_hook",
            "applied": result.applied,
            "reason": result.reason,
            "entity_id": str(result.entity_id) if result.entity_id else None,
        }
    )
    return resolved


class TurnSessionExpiredError(Exception):
    """Raised when resuming a paused turn whose LangGraph checkpoint is gone — e.g. the
    server restarted since it paused (or, before the AsyncPostgresSaver swap, simply
    because InMemorySaver never survived a restart at all). Checked structurally via
    aget_state() BEFORE ever calling ainvoke(Command(resume=...)) against a stale thread —
    confirmed live (a real reproduction, not a guess) that calling ainvoke anyway doesn't
    fail cleanly: LangGraph just treats it as a fresh run and silently re-pauses at the
    graph's *first* node, discarding every review decision already made, only surfacing
    as a crash later when some other node receives a resume value that was actually meant
    for a different step. The pre-flight check here is what actually prevents that
    class of corruption; catching an exception after the fact would be too late."""


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

    if isinstance(resume_or_initial, Command):
        pre_snapshot = await runtime.graph.aget_state(config)
        if not pre_snapshot.next:
            turn_run.status = "abandoned"
            await db.flush()
            raise TurnSessionExpiredError(str(turn_run.id))

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

    if action == "retry" and step.node_type == "roll_resolution":
        # Deterministic node — there's no prompt to retry against an LLM. "Retry" means
        # re-roll: recompute against the same ability/DC recorded in input_snapshot.
        check = step.input_snapshot.get("mechanical_check", {})
        ability_key = check.get("skill") or "str"
        ability_scores = step.input_snapshot.get("actor_context", {}).get("ability_scores", {})
        result = resolve_check(
            ability_score=ability_scores.get(ability_key, 10), dc=check.get("dc") or 10, ability=ability_key
        )
        step.raw_output = result
        await db.flush()
        return {"status": "paused", "step": step}

    if action == "retry":
        system, user = _RETRY_PROMPT_BUILDERS[step.node_type](step.input_snapshot)
        retry_model = runtime.creative_model if step.node_type in CREATIVE_NODE_TYPES else runtime.model
        out = await runtime.llm.structured_chat(
            model=retry_model, system=system, user=user, output_model=output_model
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
        resolved = await _apply_hard_pacing_floor(
            db,
            campaign_id=turn_run.campaign_id,
            resolved=resolved,
            campaign_settings=step.input_snapshot.get("campaign_settings", {}),
            turns_since_thread_activity=step.input_snapshot.get("turns_since_thread_activity", 0),
        )
        step.final_output = resolved
    elif step.node_type == "plausibility_check":
        await _apply_plausibility_time(db, campaign_id=turn_run.campaign_id, resolved=resolved)
    elif step.node_type == "tone_assessment":
        await _apply_tone_assessment(db, campaign_id=turn_run.campaign_id, resolved=resolved)
    elif step.node_type == "memory_regression":
        await _apply_memory_regression(
            db, campaign_id=turn_run.campaign_id, owner_actor_id=turn_run.actor_id, resolved=resolved,
            llm=runtime.llm,
        )

    step.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return await advance_turn(
        runtime=runtime, db=db, turn_run=turn_run, resume_or_initial=Command(resume=resolved)
    )
