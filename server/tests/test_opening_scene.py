from __future__ import annotations

import uuid

from storybard.api.turns import _generate_opening_scene
from storybard.chain.graph import ChainRuntime
from storybard.domain.actor import Actor
from storybard.domain.campaign import Campaign

MODEL = "test-model"


class TestOpeningSceneIdempotency:
    async def test_generates_once_and_stores_in_opening_narration(self, db_session, lm_client_with):
        campaign = Campaign(name="Test Campaign")
        db_session.add(campaign)
        actor = Actor(campaign_id=uuid.uuid4(), name="Arin", kind="player")
        db_session.add(actor)
        await db_session.flush()

        llm = lm_client_with({"narration": "You wake in a strange bed."})
        runtime = ChainRuntime(graph=None, llm=llm, model=MODEL)

        narration = await _generate_opening_scene(db_session, campaign=campaign, actor_id=actor.id, runtime=runtime)

        assert narration == "You wake in a strange bed."
        assert campaign.opening_narration == "You wake in a strange bed."

    async def test_second_call_does_not_call_llm_again(self, db_session, lm_client_with):
        campaign = Campaign(name="Test Campaign", opening_narration="Already set.")
        db_session.add(campaign)
        actor = Actor(campaign_id=uuid.uuid4(), name="Arin", kind="player")
        db_session.add(actor)
        await db_session.flush()

        calls = {"count": 0}

        async def fake_structured_chat(**kwargs):
            calls["count"] += 1
            raise AssertionError("should not call the LLM when summary is already set")

        llm = lm_client_with({"narration": "unused"})
        llm.structured_chat = fake_structured_chat
        runtime = ChainRuntime(graph=None, llm=llm, model=MODEL)

        narration = await _generate_opening_scene(db_session, campaign=campaign, actor_id=actor.id, runtime=runtime)

        assert narration == "Already set."
        assert calls["count"] == 0
