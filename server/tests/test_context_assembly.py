from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.chain_trace import ChainStep, TurnRun
from storybard.domain.memory import Memory
from storybard.services.context_assembly import (
    build_actor_context,
    build_recent_turns,
    build_recent_world_events,
    build_relevant_memories,
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
