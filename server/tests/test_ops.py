from __future__ import annotations

import uuid

import pytest

from storybard.chain.ops import (
    AddClockOp,
    CreateActorOp,
    CreateAncestryDefOp,
    CreateClassDefOp,
    CreateFactionOp,
    CreateItemDefOp,
    CreateMajorThreadOp,
    CreateMinorThreadOp,
    CreateSpellDefOp,
    CreateWorldNodeOp,
    ProposeHookOp,
    TickClockOp,
    UpdateActorOp,
    apply_op,
)
from storybard.core.config import settings
from storybard.domain.actor import Actor
from storybard.domain.clock import Clock
from storybard.domain.faction import Faction
from storybard.domain.hook import Hook
from storybard.domain.item import ItemDef
from storybard.domain.ruleset import AncestryDef, ClassDef
from storybard.domain.spell import SpellDef
from storybard.domain.thread import Thread
from storybard.domain.world import WorldNode


def _campaign_id() -> uuid.UUID:
    return uuid.uuid4()


class TestCreateMajorThread:
    async def test_happy_path(self, db_session):
        cid = _campaign_id()
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMajorThreadOp(
                op="create_major_thread", title="Kill the BBEG", summary="The main arc.",
                owner_type="campaign", owner_id=None,
            ),
        )
        assert result.applied is True
        thread = await db_session.get(Thread, result.entity_id)
        assert thread.tier == "major"
        assert thread.depth == 0

    async def test_cap_rejects_without_silently_no_oping(self, db_session):
        cid = _campaign_id()
        for i in range(settings.MAX_MAJOR_THREADS):
            result = await apply_op(
                db_session,
                campaign_id=cid,
                op=CreateMajorThreadOp(
                    op="create_major_thread", title=f"Arc {i}", summary="x",
                    owner_type="campaign", owner_id=None,
                ),
            )
            assert result.applied is True

        # One over the cap must be rejected, with a reason — never a silent no-op.
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMajorThreadOp(
                op="create_major_thread", title="One too many", summary="x",
                owner_type="campaign", owner_id=None,
            ),
        )
        assert result.applied is False
        assert "cap" in result.reason


class TestCreateMinorThread:
    async def _make_major(self, db_session, cid) -> uuid.UUID:
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMajorThreadOp(
                op="create_major_thread", title="Find Excalibur", summary="x",
                owner_type="campaign", owner_id=None,
            ),
        )
        return result.entity_id

    async def test_happy_path(self, db_session):
        cid = _campaign_id()
        major_id = await self._make_major(db_session, cid)
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMinorThreadOp(
                op="create_minor_thread", parent_thread_id=str(major_id), relation="prerequisite",
                title="Find the swamp caves", summary="x",
            ),
        )
        assert result.applied is True
        thread = await db_session.get(Thread, result.entity_id)
        assert thread.tier == "minor"
        assert thread.depth == 1
        assert thread.parent_thread_id == major_id

    async def test_minor_cap_rejects(self, db_session):
        cid = _campaign_id()
        major_id = await self._make_major(db_session, cid)
        for i in range(settings.MAX_MINOR_THREADS_PER_PARENT):
            result = await apply_op(
                db_session,
                campaign_id=cid,
                op=CreateMinorThreadOp(
                    op="create_minor_thread", parent_thread_id=str(major_id), relation="prerequisite",
                    title=f"Step {i}", summary="x",
                ),
            )
            assert result.applied is True

        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMinorThreadOp(
                op="create_minor_thread", parent_thread_id=str(major_id), relation="prerequisite",
                title="One too many", summary="x",
            ),
        )
        assert result.applied is False
        assert "cap" in result.reason

    async def test_depth_cap_rejects(self, db_session):
        cid = _campaign_id()
        major_id = await self._make_major(db_session, cid)
        minor_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMinorThreadOp(
                op="create_minor_thread", parent_thread_id=str(major_id), relation="prerequisite",
                title="Depth 1", summary="x",
            ),
        )
        assert minor_result.applied is True

        # Nesting a minor thread under another minor thread exceeds MAX_THREAD_DEPTH (2).
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMinorThreadOp(
                op="create_minor_thread", parent_thread_id=str(minor_result.entity_id),
                relation="prerequisite", title="Depth 2", summary="x",
            ),
        )
        assert result.applied is False
        assert "depth" in result.reason


class TestClocks:
    async def _make_thread(self, db_session, cid) -> uuid.UUID:
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateMajorThreadOp(
                op="create_major_thread", title="The Ore's Whisper", summary="x",
                owner_type="campaign", owner_id=None,
            ),
        )
        return result.entity_id

    async def test_add_and_tick_clock(self, db_session):
        cid = _campaign_id()
        thread_id = await self._make_thread(db_session, cid)
        add_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=AddClockOp(
                op="add_clock", thread_id=str(thread_id), name="Ritual completes",
                segments_total=4, tick_source="player_action", visibility="hidden",
                real_time_per_segment=None,
            ),
        )
        assert add_result.applied is True

        tick_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=TickClockOp(op="tick_clock", clock_id=str(add_result.entity_id), segments_delta=2, reason="test"),
        )
        assert tick_result.applied is True
        clock = await db_session.get(Clock, add_result.entity_id)
        assert clock.segments_filled == 2

    async def test_tick_clamps_at_total(self, db_session):
        cid = _campaign_id()
        thread_id = await self._make_thread(db_session, cid)
        add_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=AddClockOp(
                op="add_clock", thread_id=str(thread_id), name="Ritual completes",
                segments_total=2, tick_source="player_action", visibility="hidden",
                real_time_per_segment=None,
            ),
        )
        await apply_op(
            db_session,
            campaign_id=cid,
            op=TickClockOp(op="tick_clock", clock_id=str(add_result.entity_id), segments_delta=10, reason="test"),
        )
        clock = await db_session.get(Clock, add_result.entity_id)
        assert clock.segments_filled == 2

    async def test_time_elapsed_clock_parses_real_time_per_segment(self, db_session):
        from datetime import timedelta

        cid = _campaign_id()
        thread_id = await self._make_thread(db_session, cid)
        add_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=AddClockOp(
                op="add_clock", thread_id=str(thread_id), name="The blight spreads",
                segments_total=10, tick_source="time_elapsed", visibility="hidden",
                real_time_per_segment="3 days",
            ),
        )
        assert add_result.applied is True
        clock = await db_session.get(Clock, add_result.entity_id)
        assert clock.real_time_per_segment == timedelta(days=3)

    async def test_unparseable_real_time_per_segment_stays_null(self, db_session):
        cid = _campaign_id()
        thread_id = await self._make_thread(db_session, cid)
        add_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=AddClockOp(
                op="add_clock", thread_id=str(thread_id), name="The blight spreads",
                segments_total=10, tick_source="time_elapsed", visibility="hidden",
                real_time_per_segment="soon-ish",
            ),
        )
        assert add_result.applied is True
        clock = await db_session.get(Clock, add_result.entity_id)
        assert clock.real_time_per_segment is None


class TestProposeHook:
    async def test_new_canon_auto_accepts(self, db_session):
        cid = _campaign_id()
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=ProposeHookOp(
                op="propose_hook", origin="wizard's tale", proposed_text="A new rumor.",
                touches_entity_id=None,
            ),
        )
        assert result.applied is True
        hook = await db_session.get(Hook, result.entity_id)
        assert hook.status == "accepted"

    async def test_touching_existing_entity_always_needs_approval(self, db_session):
        # Even though the proposed_text reads like harmless flavor, touching an existing
        # entity must stay pending — the gate is structural (touches_entity_id set), never
        # an LLM-judged "this sounds minor" call.
        cid = _campaign_id()
        some_existing_npc_id = uuid.uuid4()
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=ProposeHookOp(
                op="propose_hook",
                origin="opportunity spotting",
                proposed_text="Just a small, harmless detail about the cat.",
                touches_entity_id=str(some_existing_npc_id),
            ),
        )
        assert result.applied is True
        hook = await db_session.get(Hook, result.entity_id)
        assert hook.status == "proposed"


class TestCreateActor:
    async def test_happy_path(self, db_session):
        cid = _campaign_id()
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateActorOp(
                op="create_actor", name="Borin", kind="npc", bio="Runs the inn.", current_node_id=None,
                current_goal="Wants to be left alone.",
            ),
        )
        assert result.applied is True
        actor = await db_session.get(Actor, result.entity_id)
        assert actor.name == "Borin"
        assert actor.kind == "npc"
        assert actor.campaign_id == cid
        assert actor.current_goal == "Wants to be left alone."

    async def test_invalid_current_node_id_fails_loudly(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateActorOp(
                op="create_actor", name="Borin", kind="npc", bio=None, current_node_id="not-a-uuid",
                current_goal=None,
            ),
        )
        assert result.applied is False
        assert "invalid" in result.reason


class TestUpdateActor:
    async def test_happy_path_updates_goal_and_bio(self, db_session):
        cid = _campaign_id()
        create_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateActorOp(
                op="create_actor", name="Tam", kind="npc", bio="A cabin boy.", current_node_id=None,
                current_goal=None,
            ),
        )
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=UpdateActorOp(
                op="update_actor", actor_id=str(create_result.entity_id),
                current_goal="Wants to warn the player about the captain.", bio=None,
            ),
        )
        assert result.applied is True
        actor = await db_session.get(Actor, create_result.entity_id)
        assert actor.current_goal == "Wants to warn the player about the captain."
        assert actor.bio == "A cabin boy."  # unchanged, since bio was null in the op

    async def test_unknown_actor_id_fails_loudly(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=UpdateActorOp(op="update_actor", actor_id=str(uuid.uuid4()), current_goal="x", bio=None),
        )
        assert result.applied is False
        assert "not found" in result.reason

    async def test_wrong_campaign_fails_loudly(self, db_session):
        # An actor id that's real but belongs to a different campaign must not be updatable
        # by this one — campaign_id scoping is enforced the same way every other lookup is.
        create_result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateActorOp(
                op="create_actor", name="Tam", kind="npc", bio=None, current_node_id=None, current_goal=None,
            ),
        )
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),  # a different campaign
            op=UpdateActorOp(op="update_actor", actor_id=str(create_result.entity_id), current_goal="x", bio=None),
        )
        assert result.applied is False
        assert "not found" in result.reason


class TestCreateWorldNode:
    async def test_root_node(self, db_session):
        cid = _campaign_id()
        result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateWorldNodeOp(
                op="create_world_node", name="Oakhaven", description="A quiet town.",
                parent_node_id=None, scale="settlement", x=None, y=None,
            ),
        )
        assert result.applied is True
        node = await db_session.get(WorldNode, result.entity_id)
        assert node.depth == 0
        assert node.parent_node_id is None

    async def test_nested_node_inherits_depth(self, db_session):
        cid = _campaign_id()
        parent_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateWorldNodeOp(
                op="create_world_node", name="Oakhaven", description=None,
                parent_node_id=None, scale="settlement", x=None, y=None,
            ),
        )
        child_result = await apply_op(
            db_session,
            campaign_id=cid,
            op=CreateWorldNodeOp(
                op="create_world_node", name="The Rusty Tankard", description="An inn.",
                parent_node_id=str(parent_result.entity_id), scale="building", x=1.0, y=2.0,
            ),
        )
        assert child_result.applied is True
        child = await db_session.get(WorldNode, child_result.entity_id)
        assert child.depth == 1
        assert child.parent_node_id == parent_result.entity_id

    async def test_missing_parent_fails_loudly(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateWorldNodeOp(
                op="create_world_node", name="Orphaned", description=None,
                parent_node_id=str(uuid.uuid4()), scale=None, x=None, y=None,
            ),
        )
        assert result.applied is False
        assert "not found" in result.reason


class TestCreateItemSpellFaction:
    async def test_create_item_def(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateItemDefOp(
                op="create_item_def", key="longsword", name="Longsword", description=None,
                item_type="weapon", properties={"damage": "1d8"},
            ),
        )
        assert result.applied is True
        item = await db_session.get(ItemDef, result.entity_id)
        assert item.key == "longsword"
        assert item.properties == {"damage": "1d8"}

    async def test_create_spell_def(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateSpellDefOp(
                op="create_spell_def", name="Fireball", description=None, level=3, school="evocation",
                casting_time="1 action", range="150 feet", duration="instantaneous", effect="Deals fire damage.",
            ),
        )
        assert result.applied is True
        spell = await db_session.get(SpellDef, result.entity_id)
        assert spell.name == "Fireball"
        assert spell.level == 3

    async def test_create_faction(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateFactionOp(
                op="create_faction", name="The Crimson Hand", description="A thieves' guild.",
                goals={"main": "control the docks"}, reputation_baseline=-10,
            ),
        )
        assert result.applied is True
        faction = await db_session.get(Faction, result.entity_id)
        assert faction.name == "The Crimson Hand"
        assert faction.reputation_baseline == -10


class TestCreateAncestryClassDef:
    async def test_create_ancestry_def(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateAncestryDefOp(
                op="create_ancestry_def", key="elf", name="Elf", description="Graceful.",
                speed=30, features={"darkvision": 60},
            ),
        )
        assert result.applied is True
        ancestry = await db_session.get(AncestryDef, result.entity_id)
        assert ancestry.key == "elf"
        assert ancestry.features == {"darkvision": 60}

    async def test_create_class_def(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateClassDefOp(
                op="create_class_def", key="wizard", name="Wizard", description="A scholar.",
                hit_die=6, primary_attribute_key="int", proficiencies={"weapons": "simple"},
                spellcasting=True, starting_equipment={"gear": "spellbook"},
            ),
        )
        assert result.applied is True
        class_def = await db_session.get(ClassDef, result.entity_id)
        assert class_def.key == "wizard"
        assert class_def.spellcasting is True


class TestUnresolvableReferences:
    async def test_minor_thread_with_missing_parent_fails_loudly(self, db_session):
        result = await apply_op(
            db_session,
            campaign_id=_campaign_id(),
            op=CreateMinorThreadOp(
                op="create_minor_thread", parent_thread_id=str(uuid.uuid4()), relation="prerequisite",
                title="Orphaned", summary="x",
            ),
        )
        assert result.applied is False
        assert "not found" in result.reason
