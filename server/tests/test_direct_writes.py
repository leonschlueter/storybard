from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select

from storybard.chain.service import _apply_memory_regression, _apply_plausibility_time, _apply_tone_assessment
from storybard.domain.actor import Actor
from storybard.domain.campaign import Campaign
from storybard.domain.memory import Memory


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
    )

    rows = (
        await db_session.execute(select(Memory).where(Memory.owner_actor_id == actor.id))
    ).scalars().all()
    assert len(rows) == 2
    assert {r.text for r in rows} == {"Borin runs the inn.", "The town smells of woodsmoke."}
