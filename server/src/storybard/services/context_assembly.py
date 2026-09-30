from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.campaign_settings import CampaignSettings
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.clock import Clock
from storybard.domain.memory import Memory
from storybard.domain.thread import Thread
from storybard.domain.thread_beat import ThreadBeat
from storybard.domain.world import WorldNode
from storybard.services.geography import ancestor_chain, nearby_locations

# Pure read/shape functions for the flat-dict catalogs fed into chain prompts. Extracted
# out of api/turns.py once there were three of these (active_threads, known_actors,
# known_locations) following the identical query-then-project pattern — see spec.md
# "Context assembly." No persistence or mutation happens here.


async def build_active_threads(db: AsyncSession, *, campaign_id: uuid.UUID) -> list[Thread]:
    return (
        (
            await db.execute(select(Thread).where(Thread.campaign_id == campaign_id, Thread.status == "active"))
        )
        .scalars()
        .all()
    )


def project_active_threads(threads: list[Thread]) -> list[dict]:
    return [{"id": str(t.id), "title": t.title, "summary": t.summary, "tier": t.tier} for t in threads]


async def build_active_clocks(db: AsyncSession, *, thread_ids: list[uuid.UUID]) -> list[dict]:
    if not thread_ids:
        return []
    clocks = (await db.execute(select(Clock).where(Clock.thread_id.in_(thread_ids)))).scalars().all()
    return [
        {
            "id": str(c.id),
            "thread_id": str(c.thread_id),
            "name": c.name,
            "segments_filled": c.segments_filled,
            "segments_total": c.segments_total,
        }
        for c in clocks
    ]


async def build_known_actors(
    db: AsyncSession, *, campaign_id: uuid.UUID, current_location_id: uuid.UUID | None = None
) -> list[dict]:
    """bio (Actor.bio) and personality (ActorProfile.personality, when set) ride along
    here so the Narrator has real per-character voice material — see narrator_prompt's
    system instruction to render dialogue distinctly per speaker (feature #13, "All 20
    Features" plan). bio is the primary source for NPCs in practice: every create_actor
    op (seeding and mid-play alike) sets it, while ActorProfile.personality is currently
    only ever populated for the player character during Party Creation — left join since
    an NPC created via create_actor has no ActorProfile row at all.

    Deliberately campaign-wide, not location-scoped — see build_scene's docstring: this
    is World Update's anti-duplication catalog, so it must include actors who aren't in
    the current scene at all. `present` (current_node_id == current_location_id) rides
    along instead so a *consuming* prompt (the Narrator) can tell "physically here" apart
    from "exists somewhere in the campaign" without losing the full catalog — confirmed
    live as the mechanism behind an NPC narrated into a scene ("has been watching from
    the shadows") with no actual staging: the Narrator had no signal that a known actor
    wasn't already present."""
    rows = (
        await db.execute(
            select(Actor, ActorProfile.personality)
            .outerjoin(ActorProfile, ActorProfile.actor_id == Actor.id)
            .where(Actor.campaign_id == campaign_id)
        )
    ).all()
    return [
        {
            "id": str(a.id), "name": a.name, "kind": a.kind, "bio": a.bio,
            "current_goal": a.current_goal, "personality": personality,
            "speech_style": a.speech_style,
            "present": current_location_id is not None and a.current_node_id == current_location_id,
        }
        for a, personality in rows
    ]


async def build_known_locations(
    db: AsyncSession, *, campaign_id: uuid.UUID, current_node_id: uuid.UUID | None
) -> list[dict]:
    """Context-budget rule (spec.md "World"): full detail for the current node, a summary
    for its immediate parent, names only for everything else — so a prompt's location
    context stays small regardless of how deep the campaign's hierarchy has grown, while
    every location's id is still present for anti-duplication reference."""
    nodes = (await db.execute(select(WorldNode).where(WorldNode.campaign_id == campaign_id))).scalars().all()
    by_id = {n.id: n for n in nodes}

    parent_id: uuid.UUID | None = None
    if current_node_id is not None:
        current = by_id.get(current_node_id)
        if current is not None:
            chain = ancestor_chain(current, by_id)
            if len(chain) >= 2:
                parent_id = chain[-2].id

    catalog = []
    for node in nodes:
        entry: dict = {
            "id": str(node.id),
            "name": node.name,
            "scale": node.scale,
            "parent_node_id": str(node.parent_node_id) if node.parent_node_id else None,
        }
        if node.id == current_node_id:
            entry["description"] = node.description
        elif node.id == parent_id:
            entry["description"] = node.description
        catalog.append(entry)
    return catalog


def build_actor_context(
    actor: Actor,
    profile: ActorProfile | None,
    sheet: CharacterSheet | None,
    *,
    personal_stakes: str | None = None,
) -> dict:
    """Flattens an Actor + its ActorProfile/CharacterSheet into the shape prompts consume
    — nothing about who the acting character *is* reached any prompt before this (see the
    "Playable Chat UI + Context-Aware Prompts" plan's Context section). Either related row
    may be missing (e.g. an NPC with no CharacterSheet); this degrades gracefully rather
    than erroring.

    personal_stakes (Campaign.personal_stakes, session-zero content) used to reach only
    opening_scene_prompt — every later turn lost it. Riding it along on actor_context means
    it now reaches every prompt actor_context already reaches, for free, no new param
    needed anywhere else. Callers pass it only for the player actor (it's campaign-wide,
    "why is the player's character here" — meaningless for an NPC)."""
    context: dict = {"name": actor.name, "kind": actor.kind, "bio": actor.bio}
    if profile is not None:
        context["appearance"] = profile.appearance
        context["personality"] = profile.personality
        context["backstory"] = profile.backstory
    if personal_stakes:
        context["personal_stakes"] = personal_stakes
    if sheet is not None:
        context["level"] = sheet.level
        context["ancestry"] = sheet.ancestry
        context["character_class"] = sheet.character_class
        context["ability_scores"] = sheet.ability_scores
        context["max_hp"] = sheet.max_hp
        context["current_hp"] = sheet.current_hp
        context["armor_class"] = sheet.armor_class
        context["conditions"] = sheet.conditions
    return context


async def build_recent_turns(db: AsyncSession, *, campaign_id: uuid.UUID, limit: int = 5) -> list[dict]:
    """The last `limit` completed turns, oldest-first — a minimal transcript so the chain
    isn't amnesiac turn-to-turn. TurnRun rows already carry action_text/final_narration;
    nothing previously read them back into a later prompt."""
    rows = (
        await db.execute(
            select(TurnRun)
            .where(TurnRun.campaign_id == campaign_id, TurnRun.status == "completed")
            # created_at, not completed_at: turns are created and completed in quick
            # sequence with no concurrent turns per actor, so ordering is equivalent, and
            # created_at is always populated (completed_at wasn't, until this same change
            # started setting it in chain/service.py::advance_turn — existing rows from
            # before that fix would sort wrong under completed_at).
            .order_by(TurnRun.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {"player_text": t.action_text, "narration": t.final_narration}
        for t in reversed(rows)
    ]


async def build_recent_world_events(db: AsyncSession, *, campaign_id: uuid.UUID, limit: int = 3) -> list[dict]:
    """What World Update actually committed on recent turns, oldest-first — closes the
    "consequences fire silently" gap: `applied_results` was already recorded on every
    `ChainStep` for audit display, but nothing ever read it back into a *future* prompt, so
    a clock filling or a Hook auto-accepting never had a chance to actually get narrated."""
    turn_ids = (
        await db.execute(
            select(TurnRun.id)
            .where(TurnRun.campaign_id == campaign_id, TurnRun.status == "completed")
            .order_by(TurnRun.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    if not turn_ids:
        return []

    steps = (
        await db.execute(
            select(ChainStep).where(ChainStep.turn_run_id.in_(turn_ids), ChainStep.node_type == "world_update")
        )
    ).scalars().all()

    events: list[dict] = []
    for step in steps:
        for result in (step.final_output or {}).get("applied_results", []):
            if result.get("applied"):
                events.append(
                    {"op": result.get("op"), "reason": result.get("reason"), "entity_id": result.get("entity_id")}
                )
    return events


# Public (not module-private) — also imported by chain/service.py's hard pacing floor
# (_apply_hard_pacing_floor) to check whether World Update already acted this turn before
# forcing anything. One definition, not two independently maintained copies.
THREAD_ACTIVITY_OPS = {"create_major_thread", "create_minor_thread", "add_clock", "tick_clock", "propose_hook"}


async def turns_since_thread_activity(db: AsyncSession, *, campaign_id: uuid.UUID, scan_limit: int = 50) -> int:
    """How many completed turns have passed since a thread/clock/hook last moved — feeds
    Plan Synthesis's stagnation check ("push a complication, don't let the scene idle").
    Scans at most `scan_limit` recent turns, most-recent-first; if none of them had thread
    activity, returns that count as a reasonable "it's been a while" signal rather than an
    unbounded scan."""
    turn_ids = (
        await db.execute(
            select(TurnRun.id)
            .where(TurnRun.campaign_id == campaign_id, TurnRun.status == "completed")
            .order_by(TurnRun.created_at.desc())
            .limit(scan_limit)
        )
    ).scalars().all()
    if not turn_ids:
        return 0

    steps = (
        await db.execute(
            select(ChainStep).where(ChainStep.turn_run_id.in_(turn_ids), ChainStep.node_type == "world_update")
        )
    ).scalars().all()
    steps_by_turn = {step.turn_run_id: step for step in steps}

    for i, turn_id in enumerate(turn_ids):
        step = steps_by_turn.get(turn_id)
        if not step:
            continue
        applied_results = (step.final_output or {}).get("applied_results", [])
        if any(r.get("applied") and r.get("op") in THREAD_ACTIVITY_OPS for r in applied_results):
            return i
    return len(turn_ids)


async def build_scene_text(
    db: AsyncSession, *, campaign_id: uuid.UUID, actor: Actor, calendar_context: str | None = None
) -> str:
    """The current-location description fed to every prompt that needs to know where the
    scene is — extracted out of api/turns.py::create_turn once a second caller (the
    opening-scene endpoint) needed the exact same logic; one copy, not two independently
    maintained ones. calendar_context (Campaign.calendar_context, when seeded) is appended
    as one more line of scene flavor — callers already have the Campaign row loaded, so it
    comes in as a parameter rather than this function re-querying it."""
    if not actor.current_node_id:
        return ""
    node = (await db.execute(select(WorldNode).where(WorldNode.id == actor.current_node_id))).scalar_one_or_none()
    if not node:
        return ""
    scene_text = f"{node.name} (danger level {node.danger_level}): {node.description or ''}"
    nearby = await nearby_locations(db, campaign_id=campaign_id, node_id=node.id, max_distance=50.0)
    if nearby:
        scene_text += "\nNearby: " + ", ".join(n.name for n in nearby[:5])
    if calendar_context:
        scene_text += f"\nCalendar: {calendar_context}"
    return scene_text


async def build_scene(db: AsyncSession, *, campaign_id: uuid.UUID, location_id: uuid.UUID | None) -> dict:
    """Compiles "what's here and what wants to happen here right now" — a single object
    for the GM to actually work from, per the "Threads, Beats, and Scene" plan. Distinct
    from build_known_actors (campaign-wide, for World Update's anti-duplication catalog):
    actors_present is filtered to who's physically at this location. due_beats surfaces
    pending ThreadBeats tied to this location, plus location-agnostic ones (location_id
    null — "applies anywhere"), so a beat isn't invisible just because the player hasn't
    reached its intended location yet. Degrades gracefully to an empty shape when
    location_id is None, matching build_scene_text's existing precedent."""
    if location_id is None:
        return {"location_name": None, "actors_present": [], "due_beats": []}

    location = (await db.execute(select(WorldNode).where(WorldNode.id == location_id))).scalar_one_or_none()

    actor_rows = (
        await db.execute(
            select(Actor).where(Actor.campaign_id == campaign_id, Actor.current_node_id == location_id)
        )
    ).scalars().all()
    actors_present = [
        {"id": str(a.id), "name": a.name, "kind": a.kind, "current_goal": a.current_goal} for a in actor_rows
    ]

    beat_rows = (
        await db.execute(
            select(ThreadBeat, Thread.title)
            .join(Thread, Thread.id == ThreadBeat.thread_id)
            .where(
                Thread.campaign_id == campaign_id,
                Thread.status == "active",
                ThreadBeat.status == "pending",
                (ThreadBeat.location_id == location_id) | (ThreadBeat.location_id.is_(None)),
            )
        )
    ).all()
    due_beats = [
        {"beat_id": str(beat.id), "thread_title": title, "description": beat.description}
        for beat, title in beat_rows
    ]

    return {"location_name": location.name if location else None, "actors_present": actors_present, "due_beats": due_beats}


async def build_npc_impressions(
    db: AsyncSession, *, campaign_id: uuid.UUID, subject_actor_id: uuid.UUID, limit: int = 5
) -> list[dict]:
    """NPC impressions of the acting player character (Memory rows with subject_actor_id
    set — the NPC-owned counterpart to build_relevant_memories) — the read side of
    feature #19, closing the same write-only-loop gap build_relevant_memories closed for
    the player's own memories."""
    rows = (
        await db.execute(
            select(Memory, Actor.name)
            .join(Actor, Actor.id == Memory.owner_actor_id)
            .where(Memory.campaign_id == campaign_id, Memory.subject_actor_id == subject_actor_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [{"npc_name": name, "text": m.text} for m, name in rows]


async def get_campaign_settings(db: AsyncSession, *, campaign_id: uuid.UUID) -> CampaignSettings:
    """The real "configurable" read path every settings-gated feature goes through —
    never a Python constant. Auto-creates a default row on first read so a campaign
    seeded before this table existed (or via the quick-dev `POST /campaigns` path, which
    doesn't create one) still gets sensible defaults rather than a missing-row error."""
    row = (
        await db.execute(select(CampaignSettings).where(CampaignSettings.campaign_id == campaign_id))
    ).scalar_one_or_none()
    if row is None:
        row = CampaignSettings(campaign_id=campaign_id)
        db.add(row)
        await db.flush()
    return row


def campaign_settings_to_dict(settings: CampaignSettings) -> dict:
    """Flat dict projection fed into ChainState as "campaign_settings" — the runtime-read
    gate every settings-controlled prompt/branch checks (chain/graph.py,
    chain/service.py), matching every other flat-dict catalog in this module."""
    return {
        "narration_npc_voices": settings.narration_npc_voices,
        "narration_npc_memory": settings.narration_npc_memory,
        "narration_consequence_ledger": settings.narration_consequence_ledger,
        "narration_hard_stagnation_threshold": settings.narration_hard_stagnation_threshold,
        "narration_oracle_enabled": settings.narration_oracle_enabled,
        "narration_twist_enabled": settings.narration_twist_enabled,
        "narration_twist_frequency": settings.narration_twist_frequency,
        "narration_npc_offscreen": settings.narration_npc_offscreen,
        "narration_npc_offscreen_interval_hours": settings.narration_npc_offscreen_interval_hours,
        "mechanical_degrees_of_success": settings.mechanical_degrees_of_success,
    }


async def build_relevant_memories(
    db: AsyncSession,
    *,
    owner_actor_id: uuid.UUID,
    limit: int = 5,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    """The acting actor's memories most relevant to the current moment — closes the
    write-only loop Memory Regression left open (it creates Memory rows; nothing read them
    back).

    query_embedding (an embedding of the current player message, computed by the caller
    via LMStudioClient.embed) turns this into a real semantic-similarity query — cosine
    distance via pgvector, ascending (closest first). Without it, falls back to the
    original importance-then-recency sort: despite the name, that sort was never actually
    "relevant" to anything — a global top-N for the actor with zero connection to the
    current scene or topic. A NULL embedding (rows written before this column existed, or
    an embed() call that failed) sorts last under Postgres's default NULLS LAST on an ASC
    ordering, so old/unembedded memories degrade to "least relevant" rather than erroring
    or vanishing."""
    query = select(Memory).where(Memory.owner_actor_id == owner_actor_id)
    if query_embedding is not None:
        query = query.order_by(Memory.embedding.cosine_distance(query_embedding))
    else:
        query = query.order_by(Memory.importance.desc(), Memory.created_at.desc())
    rows = (await db.execute(query.limit(limit))).scalars().all()
    return [{"title": m.title, "text": m.text, "importance": m.importance} for m in rows]
