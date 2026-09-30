from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Literal, Union

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.core.config import settings
from storybard.domain.actor import Actor, CharacterSheet
from storybard.domain.clock import Clock
from storybard.domain.faction import Faction
from storybard.domain.hook import Hook
from storybard.domain.item import ItemDef
from storybard.domain.ruleset import AncestryDef, ClassDef
from storybard.domain.spell import SpellDef
from storybard.domain.thread import MAX_THREAD_DEPTH, Thread
from storybard.domain.thread_beat import ThreadBeat
from storybard.domain.world import WorldNode
from storybard.services.duration import parse_duration
from storybard.services.llm.schemas import StrictOut


class BeatSpec(StrictOut):
    """A planned step in a thread's progression, staged at thread-creation time — see
    domain/thread_beat.py::ThreadBeat. Not a top-level discriminated op itself; nested
    inside CreateMajorThreadOp/CreateMinorThreadOp's initial_beats."""

    description: str
    location_id: str | None


class CreateMajorThreadOp(StrictOut):
    op: Literal["create_major_thread"]
    title: str
    summary: str
    owner_type: Literal["campaign", "actor", "faction"]
    owner_id: str | None
    # 2-4 concrete planned steps when the thread has enough shape to warrant staging one —
    # an empty list is fine and expected for a thread that's still just a premise. See
    # ThreadBeat's docstring for why abandonment doesn't carry a nested consequence field.
    initial_beats: list[BeatSpec]


class CreateMinorThreadOp(StrictOut):
    op: Literal["create_minor_thread"]
    parent_thread_id: str
    relation: Literal["prerequisite", "alternative", "optional_aid"]
    title: str
    summary: str
    initial_beats: list[BeatSpec]


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
    # How this character actually talks (vocabulary, cadence, verbal tics) — the field
    # narrator_prompt actually needs to render a distinct dialogue voice. bio is backstory,
    # not voice; ActorProfile.personality is player-only. Without this, every NPC's
    # "personality" in known_actors was structurally always null. Null is fine if the
    # character isn't expected to speak.
    speech_style: str | None


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
    # Lets an NPC's voice be established later if create_actor left it null, or refined
    # once they've actually spoken on-screen. Null leaves the existing value unchanged,
    # same convention as current_goal/bio above.
    speech_style: str | None


class ApplyDamageOp(StrictOut):
    """The concrete mechanical consequence a real roll's failure (or any narrative danger)
    can leave on a character — previously nothing in the ops vocabulary could touch
    CharacterSheet.current_hp at all. amount is positive to damage, negative to heal;
    _apply_damage clamps to [0, max_hp] rather than trusting the LLM's arithmetic. See the
    "Real Mechanical Consequences" plan."""

    op: Literal["apply_damage"]
    actor_id: str
    amount: int
    reason: str


class ApplyConditionOp(StrictOut):
    """Adds or removes a status tag (e.g. "shaken", "poisoned") from CharacterSheet.
    conditions — the persistent counterpart to ApplyDamageOp for consequences that aren't
    HP loss. active=True adds (deduped), active=False removes."""

    op: Literal["apply_condition"]
    actor_id: str
    condition: str
    active: bool
    note: str | None


class FireBeatOp(StrictOut):
    """Marks a ThreadBeat as delivered — the GM decided this planned step is happening
    now. Purely a state transition; the actual narrative content comes from the Narrator
    having been told about the beat via services/context_assembly.py::build_scene."""

    op: Literal["fire_beat"]
    beat_id: str
    reason: str


class AbandonBeatOp(StrictOut):
    """Marks a ThreadBeat as skipped rather than silently forgotten — a real, code-tracked
    event instead of decay nothing ever notices. If a real consequence is warranted, pair
    this with a sibling op in the same World Update batch (propose_hook, apply_condition,
    tick_clock, ...) rather than a nested consequence field — see ThreadBeat's docstring
    for why."""

    op: Literal["abandon_beat"]
    beat_id: str
    reason: str


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
        ApplyDamageOp,
        ApplyConditionOp,
        FireBeatOp,
        AbandonBeatOp,
    ],
    Field(discriminator="op"),
]


class WorldUpdateOut(StrictOut):
    ops: list[WorldOp]


# A strict subset of WorldOp used only for Campaign Seeding's mechanical content-generation
# LLM call (chain/seed_service.py's seed_content_prompt: races/classes/items/spells) — per
# spec.md design principle #2, grammar-constrained decoding only enforces what the JSON
# schema itself forbids, so keeping the model from proposing e.g. create_actor or
# tick_clock during seeding needs a narrower schema, not just prompt wording. Every SeedOp
# member validates as a WorldOp too (same discriminators, same fields), so the existing
# apply_op/apply_world_update_ops machinery applies unchanged.
#
# CreateFactionOp deliberately isn't here: faction seeding moved to the always-on
# seed_narrative_prompt call (SeedNarrativeOp below) so a standard_5e campaign gets a
# background faction too, not just "generate" mode (feature #6, "All 20 Features" plan).
SeedOp = Annotated[
    Union[CreateAncestryDefOp, CreateClassDefOp, CreateItemDefOp, CreateSpellDefOp],
    Field(discriminator="op"),
]


class SeedContentOut(StrictOut):
    ops: list[SeedOp]


# A second narrow subset, used only for Campaign Seeding's *narrative* content call
# (chain/seed_service.py's seed_narrative_prompt) — NPCs, Hooks/Rumors, a background
# Faction, (when seed_location_depth >= 2) child locations, and one elaborated major
# thread per must-include wish. Deliberately separate from SeedOp (mechanical content:
# ancestries/classes/items/spells) — narrative and mechanical seeding are different
# judgment calls, made in different LLM calls, so a schema mixing them would let one leak
# into the other's slot. Always called regardless of races_classes_mode, unlike SeedOp
# (per the "All 20 Features" plan, feature #1).
#
# CreateMajorThreadOp is here specifically so must-include wishes get elaborated (real
# title/summary/initial_beats) by this LLM call instead of being copied verbatim — see
# chain/seed_service.py's propose_seed, which used to construct these directly in Python
# (title=wish, summary=wish, no beats) and has since stopped, per direct user feedback
# that the resulting threads were flat and un-elaborated.
SeedNarrativeOp = Annotated[
    Union[CreateActorOp, ProposeHookOp, CreateFactionOp, CreateWorldNodeOp, CreateMajorThreadOp],
    Field(discriminator="op"),
]


class SeedNarrativeOut(StrictOut):
    """ops's create_world_node entries (when present) reference their parent by the
    parent location's plain NAME in parent_node_id, not a real id — at generation time no
    location has a real id yet. chain/seed_service.py's commit_seed resolves these names
    against already-applied locations as it applies them in order, a resolution scoped to
    seeding only (apply_op's general contract elsewhere is unchanged: always a real id).
    Same reasoning for create_actor's current_node_id: the root location's name is a valid
    placeholder there too.

    planted_reveal is a single GM-only hidden connection (chain/seed_service.py stores it
    as a PlantedReveal row, never fed to the player) — deliberately not part of the ops
    vocabulary since it isn't a piece of persistent *world* state apply_op gates, the same
    reasoning CreateMemoryOut's docstring gives for keeping Memory separate. Null when
    seed_planted_reveal is off.
    """

    ops: list[SeedNarrativeOp]
    planted_reveal: str | None


class MemoryEntry(StrictOut):
    title: str | None
    text: str
    importance: int


class NpcImpression(StrictOut):
    """A one-line "what does this NPC now think of the player" note — the NPC-owned
    counterpart to the player-owned MemoryEntry above (feature #19, "All 20 Features"
    plan). npc_actor_id must resolve to a real, campaign-scoped Actor of kind "npc"/
    "companion" or the impression is silently skipped (never a fabricated actor id
    trusted into the database) — see chain/service.py::_apply_memory_regression."""

    npc_actor_id: str
    text: str


class CreateMemoryOut(StrictOut):
    """Deliberately separate from WorldOp/apply_op — Memory Regression writes directly via
    chain/service.py, not through the Thread-focused ops vocabulary. Memory is low-stakes
    personal recollection, not persistent shared world state, so it doesn't need
    Thread-style tiering/caps. See spec.md Phase 2B plan.

    campaign_summary_update also rides along here rather than getting its own chain node:
    Memory Regression already runs last and already sees the full narration — the exact
    input a rolling "where does the story stand now" summary needs, so reusing the node
    that has that context avoids inventing a new one that would need the same wiring.

    npc_impressions similarly rides along here rather than a dedicated node — same
    reasoning, plus these are Memory rows too (just with owner/subject swapped), so the
    same node that already writes Memory writes these.
    """

    memories: list[MemoryEntry]
    campaign_summary_update: str
    npc_impressions: list[NpcImpression]


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
    if isinstance(op, ApplyDamageOp):
        return await _apply_damage(db, campaign_id=campaign_id, op=op)
    if isinstance(op, ApplyConditionOp):
        return await _apply_condition(db, campaign_id=campaign_id, op=op)
    if isinstance(op, FireBeatOp):
        return await _fire_beat(db, campaign_id=campaign_id, op=op)
    if isinstance(op, AbandonBeatOp):
        return await _abandon_beat(db, campaign_id=campaign_id, op=op)
    return AppliedOpResult(applied=False, reason=f"unknown op type: {op!r}")


async def _create_beats(
    db: AsyncSession, *, campaign_id: uuid.UUID, thread_id: uuid.UUID, beats: list[BeatSpec]
) -> None:
    """Creates the ThreadBeat rows staged alongside a new thread. A malformed or
    unresolvable location_id on one beat drops *that beat's* location link (falls back to
    "applies anywhere") rather than failing the whole thread-creation op — one bad
    reference in a list of several beats shouldn't sink the entire thread."""
    for i, beat in enumerate(beats):
        location_id: uuid.UUID | None = None
        if beat.location_id:
            parsed, err = _parse_uuid(beat.location_id, "location_id")
            if not err:
                node = (
                    await db.execute(
                        select(WorldNode).where(WorldNode.id == parsed, WorldNode.campaign_id == campaign_id)
                    )
                ).scalar_one_or_none()
                if node:
                    location_id = parsed
        db.add(
            ThreadBeat(thread_id=thread_id, order_index=i, description=beat.description, location_id=location_id)
        )
    if beats:
        await db.flush()


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
    await _create_beats(db, campaign_id=campaign_id, thread_id=thread.id, beats=op.initial_beats)
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
    await _create_beats(db, campaign_id=campaign_id, thread_id=thread.id, beats=op.initial_beats)
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
        current_goal=op.current_goal, speech_style=op.speech_style,
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
    if op.speech_style is not None:
        actor.speech_style = op.speech_style
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


async def _get_actor_and_sheet(
    db: AsyncSession, *, campaign_id: uuid.UUID, actor_id_raw: str
) -> tuple[Actor | None, CharacterSheet | None, str | None]:
    actor_id, err = _parse_uuid(actor_id_raw, "actor_id")
    if err:
        return None, None, err
    actor = (
        await db.execute(select(Actor).where(Actor.id == actor_id, Actor.campaign_id == campaign_id))
    ).scalar_one_or_none()
    if not actor:
        return None, None, f"actor {actor_id} not found"
    sheet = (await db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor.id))).scalar_one_or_none()
    if not sheet:
        return actor, None, f"actor {actor_id} has no character sheet"
    return actor, sheet, None


async def _apply_damage(db: AsyncSession, *, campaign_id: uuid.UUID, op: ApplyDamageOp) -> AppliedOpResult:
    actor, sheet, err = await _get_actor_and_sheet(db, campaign_id=campaign_id, actor_id_raw=op.actor_id)
    if err:
        return AppliedOpResult(applied=False, reason=err)
    sheet.current_hp = max(0, min(sheet.max_hp, sheet.current_hp - op.amount))
    await db.flush()
    return AppliedOpResult(applied=True, reason=f"current_hp -> {sheet.current_hp}", entity_id=actor.id)


async def _apply_condition(db: AsyncSession, *, campaign_id: uuid.UUID, op: ApplyConditionOp) -> AppliedOpResult:
    actor, sheet, err = await _get_actor_and_sheet(db, campaign_id=campaign_id, actor_id_raw=op.actor_id)
    if err:
        return AppliedOpResult(applied=False, reason=err)
    conditions = list(sheet.conditions or [])
    if op.active:
        if op.condition not in conditions:
            conditions.append(op.condition)
    else:
        conditions = [c for c in conditions if c != op.condition]
    sheet.conditions = conditions
    await db.flush()
    return AppliedOpResult(applied=True, reason=f"conditions -> {conditions}", entity_id=actor.id)


async def _get_beat(
    db: AsyncSession, *, campaign_id: uuid.UUID, beat_id_raw: str
) -> tuple[ThreadBeat | None, str | None]:
    beat_id, err = _parse_uuid(beat_id_raw, "beat_id")
    if err:
        return None, err
    beat = (
        await db.execute(
            select(ThreadBeat)
            .join(Thread, Thread.id == ThreadBeat.thread_id)
            .where(ThreadBeat.id == beat_id, Thread.campaign_id == campaign_id)
        )
    ).scalar_one_or_none()
    if not beat:
        return None, f"beat {beat_id} not found"
    return beat, None


async def _fire_beat(db: AsyncSession, *, campaign_id: uuid.UUID, op: FireBeatOp) -> AppliedOpResult:
    beat, err = await _get_beat(db, campaign_id=campaign_id, beat_id_raw=op.beat_id)
    if err:
        return AppliedOpResult(applied=False, reason=err)
    beat.status = "fired"
    await db.flush()
    return AppliedOpResult(applied=True, reason="fired", entity_id=beat.id)


async def _abandon_beat(db: AsyncSession, *, campaign_id: uuid.UUID, op: AbandonBeatOp) -> AppliedOpResult:
    beat, err = await _get_beat(db, campaign_id=campaign_id, beat_id_raw=op.beat_id)
    if err:
        return AppliedOpResult(applied=False, reason=err)
    beat.status = "abandoned"
    await db.flush()
    return AppliedOpResult(applied=True, reason="abandoned", entity_id=beat.id)
