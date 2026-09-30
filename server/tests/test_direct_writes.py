from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select

from storybard.chain.service import (
    _apply_hard_pacing_floor,
    _apply_memory_regression,
    _apply_plausibility_time,
    _apply_tone_assessment,
)
from storybard.domain.actor import Actor
from storybard.domain.campaign import Campaign
from storybard.domain.hook import Hook
from storybard.domain.memory import Memory


class _NullEmbedLLM:
    """A stub in place of LMStudioClient for tests that only care about the direct-write
    logic, not embedding — _apply_memory_regression's embed step degrades gracefully to
    None on any embed failure, so a stub that always returns None exercises exactly that
    path rather than needing a real/mocked LM Studio embeddings call."""

    async def embed(self, *, model: str, text: str) -> None:
        return None


async def test_tone_assessment_writes_directly_to_campaign(db_session):
    campaign = Campaign(name="Test Campaign")
    db_session.add(campaign)
    await db_session.flush()

    await _apply_tone_assessment(
        db_session, campaign_id=campaign.id, resolved={"tension": "quietly unsettling", "drivers": ["a rumor"]}
    )

    refreshed = await db_session.get(Campaign, campaign.id)
    assert refreshed.tone_state == {"tension": "quietly unsettling", "drivers": ["a rumor"]}


async def test_plausibility_time_advances_current_datetime(db_session):
    campaign = Campaign(name="Test Campaign")
    db_session.add(campaign)
    await db_session.flush()
    before = campaign.current_datetime

    await _apply_plausibility_time(
        db_session, campaign_id=campaign.id, resolved={"time_passed": "3 weeks"}
    )

    refreshed = await db_session.get(Campaign, campaign.id)
    assert refreshed.current_datetime == before + timedelta(weeks=3)


async def test_plausibility_time_unparseable_text_advances_nothing(db_session):
    campaign = Campaign(name="Test Campaign")
    db_session.add(campaign)
    await db_session.flush()
    before = campaign.current_datetime

    await _apply_plausibility_time(
        db_session, campaign_id=campaign.id, resolved={"time_passed": "in the blink of an eye"}
    )

    refreshed = await db_session.get(Campaign, campaign.id)
    assert refreshed.current_datetime == before


async def test_memory_regression_creates_memory_rows_no_caps(db_session):
    campaign_id = uuid.uuid4()
    actor = Actor(campaign_id=campaign_id, name="Arin", kind="player")
    db_session.add(actor)
    await db_session.flush()

    await _apply_memory_regression(
        db_session,
        campaign_id=campaign_id,
        owner_actor_id=actor.id,
        resolved={
            "memories": [
                {"title": "Met the innkeeper", "text": "Borin runs the inn.", "importance": 2},
                {"title": None, "text": "The town smells of woodsmoke.", "importance": 1},
            ]
        },
        llm=_NullEmbedLLM(),
    )

    rows = (
        await db_session.execute(select(Memory).where(Memory.owner_actor_id == actor.id))
    ).scalars().all()
    assert len(rows) == 2
    assert {r.text for r in rows} == {"Borin runs the inn.", "The town smells of woodsmoke."}


async def test_memory_regression_writes_valid_npc_impressions(db_session):
    campaign_id = uuid.uuid4()
    player = Actor(campaign_id=campaign_id, name="Arin", kind="player")
    npc = Actor(campaign_id=campaign_id, name="Borin", kind="npc")
    db_session.add_all([player, npc])
    await db_session.flush()

    await _apply_memory_regression(
        db_session,
        campaign_id=campaign_id,
        owner_actor_id=player.id,
        resolved={
            "memories": [],
            "npc_impressions": [{"npc_actor_id": str(npc.id), "text": "Trusts them now."}],
        },
        llm=_NullEmbedLLM(),
    )

    rows = (
        await db_session.execute(select(Memory).where(Memory.owner_actor_id == npc.id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].subject_actor_id == player.id
    assert rows[0].text == "Trusts them now."


async def test_memory_regression_skips_impression_with_fabricated_actor_id(db_session):
    campaign_id = uuid.uuid4()
    player = Actor(campaign_id=campaign_id, name="Arin", kind="player")
    db_session.add(player)
    await db_session.flush()

    await _apply_memory_regression(
        db_session,
        campaign_id=campaign_id,
        owner_actor_id=player.id,
        resolved={
            "memories": [],
            "npc_impressions": [{"npc_actor_id": str(uuid.uuid4()), "text": "A ghost NPC's opinion."}],
        },
        llm=_NullEmbedLLM(),
    )

    rows = (await db_session.execute(select(Memory).where(Memory.campaign_id == campaign_id))).scalars().all()
    assert rows == []


class TestHardPacingFloor:
    async def test_disabled_when_threshold_zero(self, db_session):
        campaign_id = uuid.uuid4()
        resolved = await _apply_hard_pacing_floor(
            db_session,
            campaign_id=campaign_id,
            resolved={"applied_results": []},
            campaign_settings={"narration_hard_stagnation_threshold": 0},
            turns_since_thread_activity=99,
        )
        assert resolved["applied_results"] == []

    async def test_no_op_below_threshold(self, db_session):
        campaign_id = uuid.uuid4()
        resolved = await _apply_hard_pacing_floor(
            db_session,
            campaign_id=campaign_id,
            resolved={"applied_results": []},
            campaign_settings={"narration_hard_stagnation_threshold": 5},
            turns_since_thread_activity=3,
        )
        assert resolved["applied_results"] == []

    async def test_no_op_if_world_update_already_acted(self, db_session):
        campaign_id = uuid.uuid4()
        resolved = await _apply_hard_pacing_floor(
            db_session,
            campaign_id=campaign_id,
            resolved={"applied_results": [{"op": "propose_hook", "applied": True, "reason": "accepted"}]},
            campaign_settings={"narration_hard_stagnation_threshold": 5},
            turns_since_thread_activity=10,
        )
        assert len(resolved["applied_results"]) == 1

    async def test_forces_a_hook_past_threshold_when_idle(self, db_session):
        campaign_id = uuid.uuid4()
        resolved = await _apply_hard_pacing_floor(
            db_session,
            campaign_id=campaign_id,
            resolved={"applied_results": []},
            campaign_settings={"narration_hard_stagnation_threshold": 5, "narration_oracle_enabled": True},
            turns_since_thread_activity=5,
        )
        assert len(resolved["applied_results"]) == 1
        assert resolved["applied_results"][0]["op"] == "propose_hook"
        assert resolved["applied_results"][0]["applied"] is True

        hooks = (await db_session.execute(select(Hook).where(Hook.campaign_id == campaign_id))).scalars().all()
        assert len(hooks) == 1
        assert hooks[0].origin == "hard_pacing_floor"
