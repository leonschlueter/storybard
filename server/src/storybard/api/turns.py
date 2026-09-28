from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.chain.graph import ChainRuntime
from storybard.chain.ops import TickClockOp, apply_op
from storybard.chain.prompts import opening_scene_prompt
from storybard.chain.service import advance_turn, resolve_step
from storybard.core.db import get_db
from storybard.core.ws_hub import ws_hub
from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.campaign import Campaign
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.clock import Clock
from storybard.domain.narrator import NarratorProfile
from storybard.domain.thread import Thread
from storybard.services.context_assembly import (
    build_active_clocks,
    build_active_threads,
    build_actor_context,
    build_known_actors,
    build_known_locations,
    build_recent_turns,
    build_recent_world_events,
    build_relevant_memories,
    build_scene_text,
    project_active_threads,
    turns_since_thread_activity,
)
from storybard.services.llm.schemas import NarratorOut

router = APIRouter(tags=["turns"])


def get_chain_runtime(request: Request) -> ChainRuntime:
    return request.app.state.chain_runtime


def _serialize_step(step: ChainStep) -> dict:
    return {
        "id": str(step.id),
        "turn_run_id": str(step.turn_run_id),
        "node_type": step.node_type,
        "sequence": step.sequence,
        "raw_output": step.raw_output,
        "final_output": step.final_output,
        "status": step.status,
    }


class TurnCreateIn(BaseModel):
    actor_id: uuid.UUID
    text: str


@router.post("/campaigns/{campaign_id}/turns")
async def create_turn(
    campaign_id: uuid.UUID,
    body: TurnCreateIn,
    db: AsyncSession = Depends(get_db),
    runtime: ChainRuntime = Depends(get_chain_runtime),
) -> dict:
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")

    actor = (await db.execute(select(Actor).where(Actor.id == body.actor_id))).scalar_one_or_none()
    if not actor:
        raise HTTPException(status_code=404, detail="actor_not_found")

    scene_text = await build_scene_text(db, campaign_id=campaign_id, actor=actor)

    style_description, verbosity_words = "Plain, direct, spoken-style.", 150.0
    if campaign.active_narrator_profile_id:
        narrator = (
            await db.execute(
                select(NarratorProfile).where(NarratorProfile.id == campaign.active_narrator_profile_id)
            )
        ).scalar_one_or_none()
        if narrator:
            style_description = narrator.style_description or style_description
            verbosity_words = narrator.verbosity_target_words

    active_threads_rows = await build_active_threads(db, campaign_id=campaign_id)
    active_threads = project_active_threads(active_threads_rows)
    active_clocks = await build_active_clocks(db, thread_ids=[t.id for t in active_threads_rows])
    known_actors = await build_known_actors(db, campaign_id=campaign_id)
    known_locations = await build_known_locations(
        db, campaign_id=campaign_id, current_node_id=actor.current_node_id
    )

    profile = (
        await db.execute(select(ActorProfile).where(ActorProfile.actor_id == actor.id))
    ).scalar_one_or_none()
    sheet = (
        await db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor.id))
    ).scalar_one_or_none()
    actor_context = build_actor_context(actor, profile, sheet)
    recent_turns = await build_recent_turns(db, campaign_id=campaign_id)
    relevant_memories = await build_relevant_memories(db, owner_actor_id=actor.id)
    recent_world_events = await build_recent_world_events(db, campaign_id=campaign_id)
    turns_idle = await turns_since_thread_activity(db, campaign_id=campaign_id)

    turn_run = TurnRun(campaign_id=campaign.id, actor_id=actor.id, action_text=body.text)
    db.add(turn_run)
    await db.flush()

    initial_state: dict[str, Any] = {
        "player_text": body.text,
        "mode": campaign.mode,
        "scene_text": scene_text,
        "style_description": style_description,
        "verbosity_words": verbosity_words,
        "active_threads": active_threads,
        "active_clocks": active_clocks,
        "known_actors": known_actors,
        "known_locations": known_locations,
        "previous_tone": campaign.tone_state or {},
        "actor_context": actor_context,
        "recent_turns": recent_turns,
        "relevant_memories": relevant_memories,
        "recent_world_events": recent_world_events,
        "campaign_summary": campaign.summary or "",
        "turn_count": campaign.turn_count,
        "turns_since_thread_activity": turns_idle,
    }

    result = await advance_turn(runtime=runtime, db=db, turn_run=turn_run, resume_or_initial=initial_state)
    await db.commit()

    payload = _turn_result_payload(result)
    await ws_hub.broadcast(str(campaign_id), payload)
    return {"turn_run_id": str(turn_run.id), **payload}


async def _generate_opening_scene(
    db: AsyncSession, *, campaign: Campaign, actor_id: uuid.UUID, runtime: ChainRuntime
) -> str:
    """Flush-only (no commit) — same convention as chain/service.py's and
    api/party.py::_finalize_character's functions, so the db_session test fixture's
    rollback-based isolation holds. The route below commits. Idempotent: if
    campaign.opening_narration is already set, returns it without a second LLM call.
    Deliberately separate from campaign.summary, which is the *rolling* summary Memory
    Regression rewrites every turn — conflating the two would mean summary could never
    actually roll after turn 0."""
    if campaign.opening_narration:
        return campaign.opening_narration

    actor = (await db.execute(select(Actor).where(Actor.id == actor_id))).scalar_one_or_none()
    if not actor:
        raise HTTPException(status_code=404, detail="actor_not_found")

    scene_text = await build_scene_text(db, campaign_id=campaign.id, actor=actor)
    profile = (
        await db.execute(select(ActorProfile).where(ActorProfile.actor_id == actor.id))
    ).scalar_one_or_none()
    sheet = (
        await db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor.id))
    ).scalar_one_or_none()
    actor_context = build_actor_context(actor, profile, sheet)

    system, user = opening_scene_prompt(scene_text=scene_text, actor_context=actor_context)
    out = await runtime.llm.structured_chat(
        model=runtime.model, system=system, user=user, output_model=NarratorOut
    )
    campaign.opening_narration = out.narration
    await db.flush()
    return campaign.opening_narration


@router.post("/campaigns/{campaign_id}/actors/{actor_id}/opening-scene")
async def opening_scene(
    campaign_id: uuid.UUID,
    actor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    runtime: ChainRuntime = Depends(get_chain_runtime),
) -> dict:
    """Idempotent scene-setting narration for the very start of a campaign — not a
    TurnRun/ChainStep (it's flavor preceding turn 1, not a reviewable step in the steerable
    chain). Stored in Campaign.opening_narration so a page reload doesn't regenerate a
    different intro each time.
    """
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")

    narration = await _generate_opening_scene(db, campaign=campaign, actor_id=actor_id, runtime=runtime)
    await db.commit()
    return {"narration": narration}


class StepResolveIn(BaseModel):
    action: str  # approve | edit | retry
    edited_output: dict | None = None


@router.post("/chain-steps/{step_id}/resolve")
async def resolve_chain_step(
    step_id: uuid.UUID,
    body: StepResolveIn,
    db: AsyncSession = Depends(get_db),
    runtime: ChainRuntime = Depends(get_chain_runtime),
) -> dict:
    if body.action not in ("approve", "edit", "retry"):
        raise HTTPException(status_code=400, detail="invalid_action")

    step = (await db.execute(select(ChainStep).where(ChainStep.id == step_id))).scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="step_not_found")
    if step.status not in ("pending",):
        raise HTTPException(status_code=409, detail="step_already_resolved")

    turn_run = (await db.execute(select(TurnRun).where(TurnRun.id == step.turn_run_id))).scalar_one()

    result = await resolve_step(
        runtime=runtime,
        db=db,
        step=step,
        turn_run=turn_run,
        action=body.action,
        edited_output=body.edited_output,
    )
    await db.commit()

    payload = _turn_result_payload(result)
    await ws_hub.broadcast(str(turn_run.campaign_id), payload)
    return payload


def _turn_result_payload(result: dict) -> dict:
    if result["status"] == "paused":
        return {"status": "paused", "step": _serialize_step(result["step"])}
    turn_run: TurnRun = result["turn_run"]
    return {"status": "completed", "narration": turn_run.final_narration}


@router.post("/campaigns/{campaign_id}/world-tick")
async def world_tick(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Manually-triggered per spec.md (real scheduling is Phase 5 platform scope) — but the
    segment math is now time-aware, not a flat +1: each time-elapsed clock advances by
    `elapsed_since_last_tick // real_time_per_segment` segments, so a three-week rest
    correctly fires several ticks on a fast clock and none on a slow one. See spec.md
    "What a tick actually is, now."
    """
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign_not_found")

    elapsed = campaign.current_datetime - campaign.last_world_tick_at

    active_thread_ids = (
        await db.execute(select(Thread.id).where(Thread.campaign_id == campaign_id, Thread.status == "active"))
    ).scalars().all()

    ticked: list[dict] = []
    if active_thread_ids:
        clocks = (
            await db.execute(
                select(Clock).where(Clock.thread_id.in_(active_thread_ids), Clock.tick_source == "time_elapsed")
            )
        ).scalars().all()
        for clock in clocks:
            if clock.real_time_per_segment is None:
                ticked.append(
                    {"clock_id": str(clock.id), "applied": False, "reason": "no real_time_per_segment set"}
                )
                continue
            segments_delta = elapsed // clock.real_time_per_segment
            if segments_delta <= 0:
                ticked.append({"clock_id": str(clock.id), "applied": False, "reason": "not enough time elapsed"})
                continue
            op = TickClockOp(
                op="tick_clock", clock_id=str(clock.id), segments_delta=segments_delta, reason="world sim tick"
            )
            result = await apply_op(db, campaign_id=campaign_id, op=op)
            ticked.append({"clock_id": str(clock.id), "applied": result.applied, "reason": result.reason})

    campaign.last_world_tick_at = campaign.current_datetime
    await db.commit()
    return {"ticked": ticked}
