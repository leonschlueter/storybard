from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.core.config import settings
from storybard.domain.actor import Actor
from storybard.domain.clock import Clock
from storybard.domain.faction import Faction
from storybard.domain.hook import Hook
from storybard.domain.item import ItemDef
from storybard.domain.ruleset import AncestryDef, ClassDef
from storybard.domain.spell import SpellDef
from storybard.domain.thread import MAX_THREAD_DEPTH, Thread
from storybard.domain.world import WorldNode
from storybard.services.duration import parse_duration
from storybard.services.llm.schemas import StrictOut


class CreateMajorThreadOp(StrictOut):
    op: Literal["create_major_thread"]
    title: str
    summary: str
    owner_type: Literal["campaign", "actor", "faction"]
    owner_id: str | None


class CreateMinorThreadOp(StrictOut):
    op: Literal["create_minor_thread"]
    parent_thread_id: str
    relation: Literal["prerequisite", "alternative", "optional_aid"]
    title: str
    summary: str


class AddClockOp(StrictOut):
    op: Literal["add_clock"]
    thread_id: str
    name: str
    segments_total: int
    tick_source: Literal["time_elapsed", "player_action", "linked_thread_complete"]
    visibility: Literal["hidden", "player_visible"]
    # Free text ("3 days", "2 weeks") — only meaningful when tick_source="time_elapsed";
    # parsed via services/duration.py, same as Plausibility Check's time_passed. Required
    # (not omittable) per the StrictOut rule, but null is fine for non-time_elapsed clocks.
    real_time_per_segment: str | None


class TickClockOp(StrictOut):
    op: Literal["tick_clock"]
    clock_id: str
    segments_delta: int
    reason: str


class ProposeHookOp(StrictOut):
    op: Literal["propose_hook"]
    origin: str
    proposed_text: str
    touches_entity_id: str | None


# Entity-creation ops. Same StrictOut/apply_op pattern as the Thread ops above — no new
# mechanism. Unlike Thread creation, these are NOT capped: entities don't have Thread's
# fractal-explosion risk (spec.md "Entity creation"). The guard against near-duplicate
# entities is the known-actors/known-locations catalog fed into the prompt, not a numeric
# limit enforced here. This is also, deliberately, the exact mechanism Campaign Seeding
# reuses (see api/campaigns.py) rather than a separate bespoke seeder.


class CreateActorOp(StrictOut):
    op: Literal["create_actor"]
    name: str
    kind: Literal["npc", "companion"]  # never "player" — the chain doesn't create those
    bio: str | None
    current_node_id: str | None
    # A persistent one-line "what does this character want right now" note — keeps the NPC
    # playable consistently across many future turns instead of a motive reinvented from
    # bio each time. Null is fine if the narration didn't establish anything specific yet.
    current_goal: str | None


class CreateWorldNodeOp(StrictOut):
    op: Literal["create_world_node"]
    name: str
    description: str | None
    parent_node_id: str | None
    scale: str | None
    x: float | None
    y: float | None


class CreateItemDefOp(StrictOut):
    op: Literal["create_item_def"]
    key: str
    name: str
    description: str | None
    item_type: str
    properties: dict


class CreateSpellDefOp(StrictOut):
    op: Literal["create_spell_def"]
    name: str
    description: str | None
    level: int
    school: str
    casting_time: str
    range: str
    duration: str
    effect: str


class CreateFactionOp(StrictOut):
    op: Literal["create_faction"]
    name: str
    description: str | None
    goals: dict
    reputation_baseline: int


class CreateAncestryDefOp(StrictOut):
    op: Literal["create_ancestry_def"]
    key: str
    name: str
    description: str | None
    speed: int
    features: dict


class CreateClassDefOp(StrictOut):
    op: Literal["create_class_def"]
    key: str
    name: str
    description: str | None
    hit_die: int
    primary_attribute_key: str
    proficiencies: dict
    spellcasting: bool
    starting_equipment: dict


class UpdateActorOp(StrictOut):
    """The "update an existing entity" op spec.md's Entity Creation section anticipated
    but never built. Unlike a create op, this always references something that must
    already exist — the gate is structural (actor_id must resolve to a real Actor in this
    campaign, or the op is rejected with a reason), the same "never trust the LLM, enforce
    in code" principle as every cap/gate elsewhere. Mainly exists to let an NPC's
    current_goal evolve as the story moves, instead of being frozen at creation."""

    op: Literal["update_actor"]
    actor_id: str
    current_goal: str | None
    bio: str | None


WorldOp = Annotated[
    Union[
        CreateMajorThreadOp,
        CreateMinorThreadOp,
        AddClockOp,
        TickClockOp,
        ProposeHookOp,
        CreateActorOp,
        UpdateActorOp,
        CreateWorldNodeOp,
        CreateItemDefOp,
        CreateSpellDefOp,
        CreateFactionOp,
        CreateAncestryDefOp,
        CreateClassDefOp,
    ],
    Field(discriminator="op"),
]


class WorldUpdateOut(StrictOut):
    ops: list[WorldOp]


# A strict subset of WorldOp used only for Campaign Seeding's content-generation LLM call
# (chain/seed_service.py) — per spec.md design principle #2, grammar-constrained decoding
# only enforces what the JSON schema itself forbids, so keeping the model from proposing
# e.g. create_actor or tick_clock during seeding needs a narrower schema, not just prompt
# wording. Every SeedOp member validates as a WorldOp too (same discriminators, same
# fields), so the existing apply_op/apply_world_update_ops machinery applies unchanged.
SeedOp = Annotated[
    Union[CreateAncestryDefOp, CreateClassDefOp, CreateItemDefOp, CreateSpellDefOp, CreateFactionOp],
    Field(discriminator="op"),
]


class SeedContentOut(StrictOut):
    ops: list[SeedOp]


class MemoryEntry(StrictOut):
    title: str | None
    text: str
    importance: int


class CreateMemoryOut(StrictOut):
    """Deliberately separate from WorldOp/apply_op — Memory Regression writes directly via
    chain/service.py, not through the Thread-focused ops vocabulary. Memory is low-stakes
    personal recollection, not persistent shared world state, so it doesn't need
    Thread-style tiering/caps. See spec.md Phase 2B plan.

    campaign_summary_update also rides along here rather than getting its own chain node:
    Memory Regression already runs last and already sees the full narration — the exact
    input a rolling "where does the story stand now" summary needs, so reusing the node
    that has that context avoids inventing a new one that would need the same wiring.
    """

    memories: list[MemoryEntry]
    campaign_summary_update: str


@dataclass
class AppliedOpResult:
    applied: bool
    reason: str
    entity_id: uuid.UUID | None = None


def _parse_uuid(value: str, field_name: str) -> tuple[uuid.UUID | None, str | None]:
    try:
        return uuid.UUID(value), None
    except ValueError:
        return None, f"invalid {field_name}: {value!r} is not a valid id"


async def apply_op(db: AsyncSession, *, campaign_id: uuid.UUID, op: WorldOp) -> AppliedOpResult:
    """Applies one world-mutating op, enforcing every cap/gate in code — never trusted to
    the LLM (spec principle #1). A rejected op returns a clear reason; it never silently
    no-ops (spec principle #2 / the exact bug class this whole rewrite exists to avoid).
    """
    if isinstance(op, CreateMajorThreadOp):
        return await _create_major_thread(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateMinorThreadOp):
        return await _create_minor_thread(db, campaign_id=campaign_id, op=op)
    if isinstance(op, AddClockOp):
        return await _add_clock(db, campaign_id=campaign_id, op=op)
    if isinstance(op, TickClockOp):
        return await _tick_clock(db, campaign_id=campaign_id, op=op)
    if isinstance(op, ProposeHookOp):
        return await _propose_hook(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateActorOp):
        return await _create_actor(db, campaign_id=campaign_id, op=op)
    if isinstance(op, UpdateActorOp):
        return await _update_actor(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateWorldNodeOp):
        return await _create_world_node(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateItemDefOp):
        return await _create_item_def(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateSpellDefOp):
        return await _create_spell_def(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateFactionOp):
        return await _create_faction(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateAncestryDefOp):
        return await _create_ancestry_def(db, campaign_id=campaign_id, op=op)
    if isinstance(op, CreateClassDefOp):
        return await _create_class_def(db, campaign_id=campaign_id, op=op)
    return AppliedOpResult(applied=False, reason=f"unknown op type: {op!r}")


async def _create_major_thread(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateMajorThreadOp) -> AppliedOpResult:
    active_count = (
        await db.execute(
            select(func.count())
            .select_from(Thread)
            .where(Thread.campaign_id == campaign_id, Thread.tier == "major", Thread.status == "active")
        )
    ).scalar_one()
    if active_count >= settings.MAX_MAJOR_THREADS:
        return AppliedOpResult(
            applied=False,
            reason=f"major thread cap reached ({active_count}/{settings.MAX_MAJOR_THREADS} active)",
        )

    owner_id, err = (None, None)
    if op.owner_id is not None:
        owner_id, err = _parse_uuid(op.owner_id, "owner_id")
        if err:
            return AppliedOpResult(applied=False, reason=err)

    thread = Thread(
        campaign_id=campaign_id,
        title=op.title,
        summary=op.summary,
        status="active",
        tier="major",
        depth=0,
        owner_type=op.owner_type,
        owner_id=owner_id,
    )
    db.add(thread)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=thread.id)


async def _create_minor_thread(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateMinorThreadOp) -> AppliedOpResult:
    parent_id, err = _parse_uuid(op.parent_thread_id, "parent_thread_id")
    if err:
        return AppliedOpResult(applied=False, reason=err)

    parent = (
        await db.execute(select(Thread).where(Thread.id == parent_id, Thread.campaign_id == campaign_id))
    ).scalar_one_or_none()
    if not parent:
        return AppliedOpResult(applied=False, reason=f"parent thread {parent_id} not found")

    if parent.depth + 1 > MAX_THREAD_DEPTH:
        return AppliedOpResult(applied=False, reason=f"max thread depth ({MAX_THREAD_DEPTH}) exceeded")

    open_minor_count = (
        await db.execute(
            select(func.count())
            .select_from(Thread)
            .where(Thread.parent_thread_id == parent.id, Thread.status == "active")
        )
    ).scalar_one()
    if open_minor_count >= settings.MAX_MINOR_THREADS_PER_PARENT:
        return AppliedOpResult(
            applied=False,
            reason=(
                f"minor thread cap reached for parent {parent.id} "
                f"({open_minor_count}/{settings.MAX_MINOR_THREADS_PER_PARENT} open)"
            ),
        )

    thread = Thread(
        campaign_id=campaign_id,
        title=op.title,
        summary=op.summary,
        status="active",
        tier="minor",
        depth=parent.depth + 1,
        parent_thread_id=parent.id,
        relation=op.relation,
        owner_type=parent.owner_type,
        owner_id=parent.owner_id,
    )
    db.add(thread)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=thread.id)


async def _add_clock(db: AsyncSession, *, campaign_id: uuid.UUID, op: AddClockOp) -> AppliedOpResult:
    thread_id, err = _parse_uuid(op.thread_id, "thread_id")
    if err:
        return AppliedOpResult(applied=False, reason=err)

    thread = (
        await db.execute(select(Thread).where(Thread.id == thread_id, Thread.campaign_id == campaign_id))
    ).scalar_one_or_none()
    if not thread:
        return AppliedOpResult(applied=False, reason=f"thread {thread_id} not found")

    real_time_per_segment = None
    if op.real_time_per_segment is not None:
        parsed = parse_duration(op.real_time_per_segment)
        real_time_per_segment = parsed if parsed.total_seconds() > 0 else None

    clock = Clock(
        thread_id=thread.id,
        name=op.name,
        segments_total=op.segments_total,
        segments_filled=0,
        tick_source=op.tick_source,
        visibility=op.visibility,
        real_time_per_segment=real_time_per_segment,
    )
    db.add(clock)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=clock.id)


async def _tick_clock(db: AsyncSession, *, campaign_id: uuid.UUID, op: TickClockOp) -> AppliedOpResult:
    clock_id, err = _parse_uuid(op.clock_id, "clock_id")
    if err:
        return AppliedOpResult(applied=False, reason=err)

    clock = (await db.execute(select(Clock).where(Clock.id == clock_id))).scalar_one_or_none()
    if not clock:
        return AppliedOpResult(applied=False, reason=f"clock {clock_id} not found")

    clock.segments_filled = min(clock.segments_total, max(0, clock.segments_filled + op.segments_delta))
    await db.flush()

    if clock.segments_filled >= clock.segments_total and clock.consequence_op:
        consequence = _parse_op(clock.consequence_op)
        if consequence:
            await apply_op(db, campaign_id=campaign_id, op=consequence)

    return AppliedOpResult(applied=True, reason="ticked", entity_id=clock.id)


async def _propose_hook(db: AsyncSession, *, campaign_id: uuid.UUID, op: ProposeHookOp) -> AppliedOpResult:
    touches_entity_id: uuid.UUID | None = None
    if op.touches_entity_id is not None:
        touches_entity_id, err = _parse_uuid(op.touches_entity_id, "touches_entity_id")
        if err:
            return AppliedOpResult(applied=False, reason=err)

    # The gate is structural, not an LLM-judged severity score (spec.md "Hooks"): touching
    # an existing entity ALWAYS stays pending for human approval, regardless of anything the
    # LLM said about it; only new-canon proposals are eligible for auto-accept.
    hook = Hook(
        campaign_id=campaign_id,
        origin=op.origin,
        proposed_text=op.proposed_text,
        touches_entity_id=touches_entity_id,
        status="proposed" if touches_entity_id is not None else "accepted",
    )
    db.add(hook)
    await db.flush()
    return AppliedOpResult(applied=True, reason=hook.status, entity_id=hook.id)


async def _create_actor(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateActorOp) -> AppliedOpResult:
    current_node_id: uuid.UUID | None = None
    if op.current_node_id is not None:
        current_node_id, err = _parse_uuid(op.current_node_id, "current_node_id")
        if err:
            return AppliedOpResult(applied=False, reason=err)

    actor = Actor(
        campaign_id=campaign_id, name=op.name, kind=op.kind, bio=op.bio, current_node_id=current_node_id,
        current_goal=op.current_goal,
    )
    db.add(actor)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=actor.id)


async def _update_actor(db: AsyncSession, *, campaign_id: uuid.UUID, op: UpdateActorOp) -> AppliedOpResult:
    actor_id, err = _parse_uuid(op.actor_id, "actor_id")
    if err:
        return AppliedOpResult(applied=False, reason=err)

    actor = (
        await db.execute(select(Actor).where(Actor.id == actor_id, Actor.campaign_id == campaign_id))
    ).scalar_one_or_none()
    if not actor:
        return AppliedOpResult(applied=False, reason=f"actor {actor_id} not found")

    if op.current_goal is not None:
        actor.current_goal = op.current_goal
    if op.bio is not None:
        actor.bio = op.bio
    await db.flush()
    return AppliedOpResult(applied=True, reason="updated", entity_id=actor.id)


async def _create_world_node(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateWorldNodeOp) -> AppliedOpResult:
    parent: WorldNode | None = None
    if op.parent_node_id is not None:
        parent_id, err = _parse_uuid(op.parent_node_id, "parent_node_id")
        if err:
            return AppliedOpResult(applied=False, reason=err)
        parent = (
            await db.execute(select(WorldNode).where(WorldNode.id == parent_id, WorldNode.campaign_id == campaign_id))
        ).scalar_one_or_none()
        if not parent:
            return AppliedOpResult(applied=False, reason=f"parent world node {parent_id} not found")

    node = WorldNode(
        campaign_id=campaign_id,
        name=op.name,
        description=op.description,
        parent_node_id=parent.id if parent else None,
        depth=parent.depth + 1 if parent else 0,
        scale=op.scale,
        x=op.x,
        y=op.y,
    )
    db.add(node)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=node.id)


async def _create_item_def(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateItemDefOp) -> AppliedOpResult:
    item = ItemDef(
        campaign_id=campaign_id,
        key=op.key,
        name=op.name,
        description=op.description,
        item_type=op.item_type,
        properties=op.properties,
    )
    db.add(item)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=item.id)


async def _create_spell_def(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateSpellDefOp) -> AppliedOpResult:
    spell = SpellDef(
        campaign_id=campaign_id,
        name=op.name,
        description=op.description,
        level=op.level,
        school=op.school,
        casting_time=op.casting_time,
        range=op.range,
        duration=op.duration,
        effect=op.effect,
    )
    db.add(spell)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=spell.id)


async def _create_faction(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateFactionOp) -> AppliedOpResult:
    faction = Faction(
        campaign_id=campaign_id,
        name=op.name,
        description=op.description,
        goals=op.goals,
        reputation_baseline=op.reputation_baseline,
    )
    db.add(faction)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=faction.id)


async def _create_ancestry_def(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateAncestryDefOp) -> AppliedOpResult:
    ancestry = AncestryDef(
        campaign_id=campaign_id,
        key=op.key,
        name=op.name,
        description=op.description,
        speed=op.speed,
        features=op.features,
    )
    db.add(ancestry)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=ancestry.id)


async def _create_class_def(db: AsyncSession, *, campaign_id: uuid.UUID, op: CreateClassDefOp) -> AppliedOpResult:
    class_def = ClassDef(
        campaign_id=campaign_id,
        key=op.key,
        name=op.name,
        description=op.description,
        hit_die=op.hit_die,
        primary_attribute_key=op.primary_attribute_key,
        proficiencies=op.proficiencies,
        spellcasting=op.spellcasting,
        starting_equipment=op.starting_equipment,
    )
    db.add(class_def)
    await db.flush()
    return AppliedOpResult(applied=True, reason="created", entity_id=class_def.id)


def _parse_op(raw: dict) -> WorldOp | None:
    try:
        return TypeAdapter(WorldOp).validate_python(raw)
    except Exception:
        return None
