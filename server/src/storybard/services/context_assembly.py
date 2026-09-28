from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.clock import Clock
from storybard.domain.memory import Memory
from storybard.domain.thread import Thread
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


async def build_known_actors(db: AsyncSession, *, campaign_id: uuid.UUID) -> list[dict]:
    actors = (await db.execute(select(Actor).where(Actor.campaign_id == campaign_id))).scalars().all()
    return [
        {"id": str(a.id), "name": a.name, "kind": a.kind, "current_goal": a.current_goal} for a in actors
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
    actor: Actor, profile: ActorProfile | None, sheet: CharacterSheet | None
) -> dict:
    """Flattens an Actor + its ActorProfile/CharacterSheet into the shape prompts consume
    — nothing about who the acting character *is* reached any prompt before this (see the
    "Playable Chat UI + Context-Aware Prompts" plan's Context section). Either related row
    may be missing (e.g. an NPC with no CharacterSheet); this degrades gracefully rather
    than erroring."""
    context: dict = {"name": actor.name, "kind": actor.kind, "bio": actor.bio}
    if profile is not None:
        context["appearance"] = profile.appearance
        context["personality"] = profile.personality
        context["backstory"] = profile.backstory
    if sheet is not None:
        context["level"] = sheet.level
        context["ancestry"] = sheet.ancestry
        context["character_class"] = sheet.character_class
        context["ability_scores"] = sheet.ability_scores
        context["max_hp"] = sheet.max_hp
        context["current_hp"] = sheet.current_hp
        context["armor_class"] = sheet.armor_class
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


_THREAD_ACTIVITY_OPS = {"create_major_thread", "create_minor_thread", "add_clock", "tick_clock", "propose_hook"}


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
        if any(r.get("applied") and r.get("op") in _THREAD_ACTIVITY_OPS for r in applied_results):
            return i
    return len(turn_ids)


async def build_scene_text(db: AsyncSession, *, campaign_id: uuid.UUID, actor: Actor) -> str:
    """The current-location description fed to every prompt that needs to know where the
    scene is — extracted out of api/turns.py::create_turn once a second caller (the
    opening-scene endpoint) needed the exact same logic; one copy, not two independently
    maintained ones."""
    if not actor.current_node_id:
        return ""
    node = (await db.execute(select(WorldNode).where(WorldNode.id == actor.current_node_id))).scalar_one_or_none()
    if not node:
        return ""
    scene_text = f"{node.name} (danger level {node.danger_level}): {node.description or ''}"
    nearby = await nearby_locations(db, campaign_id=campaign_id, node_id=node.id, max_distance=50.0)
    if nearby:
        scene_text += "\nNearby: " + ", ".join(n.name for n in nearby[:5])
    return scene_text


async def build_relevant_memories(db: AsyncSession, *, owner_actor_id: uuid.UUID, limit: int = 5) -> list[dict]:
    """The acting actor's most important/recent memories — closes the write-only loop
    Memory Regression left open (it creates Memory rows; nothing read them back)."""
    rows = (
        await db.execute(
            select(Memory)
            .where(Memory.owner_actor_id == owner_actor_id)
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [{"title": m.title, "text": m.text, "importance": m.importance} for m in rows]
