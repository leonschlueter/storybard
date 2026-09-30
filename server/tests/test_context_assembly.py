from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.memory import Memory
from storybard.domain.thread import Thread
from storybard.domain.thread_beat import ThreadBeat
from storybard.domain.world import WorldNode
from storybard.services.context_assembly import (
    build_actor_context,
    build_known_actors,
    build_recent_turns,
    build_recent_world_events,
    build_relevant_memories,
    build_scene,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestBuildActorContext:
    def test_actor_only_degrades_gracefully(self):
        actor = Actor(campaign_id=uuid.uuid4(), name="Borin", kind="npc", bio="Runs the inn.")
        context = build_actor_context(actor, None, None)
        assert context == {"name": "Borin", "kind": "npc", "bio": "Runs the inn."}

    def test_with_profile_and_sheet(self):
        actor = Actor(campaign_id=uuid.uuid4(), name="Arin", kind="player", bio=None)
        profile = ActorProfile(actor_id=actor.id, appearance="Tall", personality="Blunt", backstory="A wanderer.")
        sheet = CharacterSheet(
            actor_id=actor.id, level=2, ancestry="Elf", character_class="Wizard",
            ability_scores={"int": 16}, max_hp=12, current_hp=8, armor_class=13,
        )
        context = build_actor_context(actor, profile, sheet)
        assert context["appearance"] == "Tall"
        assert context["ancestry"] == "Elf"
        assert context["level"] == 2
        assert context["max_hp"] == 12
        assert context["current_hp"] == 8

    def test_personal_stakes_included_when_given(self):
        actor = Actor(campaign_id=uuid.uuid4(), name="Arin", kind="player", bio=None)
        context = build_actor_context(actor, None, None, personal_stakes="Avenge her sister.")
        assert context["personal_stakes"] == "Avenge her sister."

    def test_personal_stakes_omitted_when_none(self):
        actor = Actor(campaign_id=uuid.uuid4(), name="Borin", kind="npc", bio="Runs the inn.")
        context = build_actor_context(actor, None, None)
        assert "personal_stakes" not in context


class TestBuildRecentTurns:
    async def test_returns_oldest_first_and_respects_limit(self, db_session):
        campaign_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        base = _now()
        for i in range(5):
            db_session.add(
                TurnRun(
                    campaign_id=campaign_id, actor_id=actor_id, action_text=f"action {i}",
                    status="completed", final_narration=f"narration {i}",
                    created_at=base + timedelta(minutes=i), completed_at=base + timedelta(minutes=i),
                )
            )
        await db_session.flush()

        recent = await build_recent_turns(db_session, campaign_id=campaign_id, limit=3)

        assert len(recent) == 3
        assert [t["player_text"] for t in recent] == ["action 2", "action 3", "action 4"]

    async def test_excludes_incomplete_turns(self, db_session):
        campaign_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        db_session.add(
            TurnRun(campaign_id=campaign_id, actor_id=actor_id, action_text="paused one", status="paused")
        )
        await db_session.flush()

        recent = await build_recent_turns(db_session, campaign_id=campaign_id)
        assert recent == []


class TestBuildRelevantMemories:
    async def test_orders_by_importance_then_recency(self, db_session):
        campaign_id = uuid.uuid4()
        actor = Actor(campaign_id=campaign_id, name="Arin", kind="player")
        db_session.add(actor)
        await db_session.flush()
        actor_id = actor.id
        base = _now()
        db_session.add(
            Memory(
                campaign_id=campaign_id, owner_actor_id=actor_id, title="Old important",
                text="An old important memory.", importance=5, created_at=base,
            )
        )
        db_session.add(
            Memory(
                campaign_id=campaign_id, owner_actor_id=actor_id, title="New important",
                text="A newer important memory.", importance=5, created_at=base + timedelta(hours=1),
            )
        )
        db_session.add(
            Memory(
                campaign_id=campaign_id, owner_actor_id=actor_id, title="Trivial",
                text="A trivial memory.", importance=1, created_at=base + timedelta(hours=2),
            )
        )
        await db_session.flush()

        memories = await build_relevant_memories(db_session, owner_actor_id=actor_id)

        assert [m["title"] for m in memories] == ["New important", "Old important", "Trivial"]

    async def test_respects_limit(self, db_session):
        campaign_id = uuid.uuid4()
        actor = Actor(campaign_id=campaign_id, name="Arin", kind="player")
        db_session.add(actor)
        await db_session.flush()
        actor_id = actor.id
        for i in range(10):
            db_session.add(
                Memory(
                    campaign_id=campaign_id, owner_actor_id=actor_id, title=f"m{i}",
                    text="x", importance=1,
                )
            )
        await db_session.flush()

        memories = await build_relevant_memories(db_session, owner_actor_id=actor_id, limit=4)
        assert len(memories) == 4


class TestBuildRecentWorldEvents:
    async def test_only_applied_results_surface(self, db_session):
        campaign_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        turn = TurnRun(
            campaign_id=campaign_id, actor_id=actor_id, action_text="x",
            status="completed", final_narration="y",
        )
        db_session.add(turn)
        await db_session.flush()
        db_session.add(
            ChainStep(
                turn_run_id=turn.id, node_type="world_update", sequence=7,
                final_output={
                    "applied_results": [
                        {"op": "create_actor", "applied": True, "reason": "created", "entity_id": "1"},
                        {"op": "create_major_thread", "applied": False, "reason": "cap reached", "entity_id": None},
                    ]
                },
            )
        )
        await db_session.flush()

        events = await build_recent_world_events(db_session, campaign_id=campaign_id)

        assert len(events) == 1
        assert events[0]["op"] == "create_actor"

    async def test_respects_limit_across_turns(self, db_session):
        campaign_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        base = datetime.now(timezone.utc)
        for i in range(5):
            turn = TurnRun(
                campaign_id=campaign_id, actor_id=actor_id, action_text=f"a{i}",
                status="completed", final_narration="y", created_at=base + timedelta(minutes=i),
            )
            db_session.add(turn)
            await db_session.flush()
            db_session.add(
                ChainStep(
                    turn_run_id=turn.id, node_type="world_update", sequence=7,
                    final_output={
                        "applied_results": [
                            {"op": f"op{i}", "applied": True, "reason": "created", "entity_id": None}
                        ]
                    },
                )
            )
        await db_session.flush()

        events = await build_recent_world_events(db_session, campaign_id=campaign_id, limit=2)

        assert len(events) == 2
        assert {e["op"] for e in events} == {"op3", "op4"}

    async def test_no_completed_turns_returns_empty(self, db_session):
        events = await build_recent_world_events(db_session, campaign_id=uuid.uuid4())
        assert events == []


class TestBuildKnownActors:
    async def test_present_flag_reflects_current_location(self, db_session):
        campaign_id = uuid.uuid4()
        here = WorldNode(campaign_id=campaign_id, name="Here", description=None)
        elsewhere = WorldNode(campaign_id=campaign_id, name="Elsewhere", description=None)
        db_session.add_all([here, elsewhere])
        await db_session.flush()
        db_session.add_all(
            [
                Actor(campaign_id=campaign_id, name="Here NPC", kind="npc", current_node_id=here.id),
                Actor(campaign_id=campaign_id, name="Elsewhere NPC", kind="npc", current_node_id=elsewhere.id),
                Actor(campaign_id=campaign_id, name="Unplaced NPC", kind="npc", current_node_id=None),
            ]
        )
        await db_session.flush()

        actors = await build_known_actors(db_session, campaign_id=campaign_id, current_location_id=here.id)

        by_name = {a["name"]: a["present"] for a in actors}
        assert by_name["Here NPC"] is True
        assert by_name["Elsewhere NPC"] is False
        assert by_name["Unplaced NPC"] is False

    async def test_no_current_location_marks_everyone_absent(self, db_session):
        campaign_id = uuid.uuid4()
        db_session.add(Actor(campaign_id=campaign_id, name="Someone", kind="npc"))
        await db_session.flush()

        actors = await build_known_actors(db_session, campaign_id=campaign_id)

        assert actors[0]["present"] is False


class TestBuildScene:
    async def test_none_location_returns_empty_shape(self, db_session):
        scene = await build_scene(db_session, campaign_id=uuid.uuid4(), location_id=None)
        assert scene == {"location_name": None, "actors_present": [], "due_beats": []}

    async def test_actors_filtered_to_this_location_only(self, db_session):
        campaign_id = uuid.uuid4()
        here = WorldNode(campaign_id=campaign_id, name="Here", description=None)
        elsewhere = WorldNode(campaign_id=campaign_id, name="Elsewhere", description=None)
        db_session.add_all([here, elsewhere])
        await db_session.flush()
        db_session.add(Actor(campaign_id=campaign_id, name="Present", kind="npc", current_node_id=here.id))
        db_session.add(Actor(campaign_id=campaign_id, name="Absent", kind="npc", current_node_id=elsewhere.id))
        await db_session.flush()

        scene = await build_scene(db_session, campaign_id=campaign_id, location_id=here.id)

        assert scene["location_name"] == "Here"
        assert [a["name"] for a in scene["actors_present"]] == ["Present"]

    async def test_due_beats_include_location_specific_and_location_agnostic(self, db_session):
        campaign_id = uuid.uuid4()
        here = WorldNode(campaign_id=campaign_id, name="Here", description=None)
        elsewhere = WorldNode(campaign_id=campaign_id, name="Elsewhere", description=None)
        db_session.add_all([here, elsewhere])
        await db_session.flush()
        thread = Thread(campaign_id=campaign_id, title="A Thread", summary="x", status="active", tier="major")
        db_session.add(thread)
        await db_session.flush()
        db_session.add_all([
            ThreadBeat(thread_id=thread.id, order_index=0, description="Happens here", location_id=here.id),
            ThreadBeat(thread_id=thread.id, order_index=1, description="Happens elsewhere", location_id=elsewhere.id),
            ThreadBeat(thread_id=thread.id, order_index=2, description="Applies anywhere", location_id=None),
        ])
        await db_session.flush()

        scene = await build_scene(db_session, campaign_id=campaign_id, location_id=here.id)

        descriptions = {b["description"] for b in scene["due_beats"]}
        assert descriptions == {"Happens here", "Applies anywhere"}
        assert all(b["thread_title"] == "A Thread" for b in scene["due_beats"])

    async def test_fired_beats_and_inactive_threads_excluded(self, db_session):
        campaign_id = uuid.uuid4()
        here = WorldNode(campaign_id=campaign_id, name="Here", description=None)
        db_session.add(here)
        await db_session.flush()
        active_thread = Thread(campaign_id=campaign_id, title="Active", summary="x", status="active", tier="major")
        resolved_thread = Thread(campaign_id=campaign_id, title="Resolved", summary="x", status="resolved", tier="major")
        db_session.add_all([active_thread, resolved_thread])
        await db_session.flush()
        db_session.add_all([
            ThreadBeat(thread_id=active_thread.id, order_index=0, description="Already fired", location_id=here.id, status="fired"),
            ThreadBeat(thread_id=resolved_thread.id, order_index=0, description="Dead thread", location_id=here.id, status="pending"),
        ])
        await db_session.flush()

        scene = await build_scene(db_session, campaign_id=campaign_id, location_id=here.id)
        assert scene["due_beats"] == []
