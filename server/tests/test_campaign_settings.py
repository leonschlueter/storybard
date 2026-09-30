from __future__ import annotations

import uuid

from sqlalchemy import select

from storybard.chain.seed_service import SeedInput, commit_seed, propose_seed
from storybard.domain.campaign_settings import CampaignSettings
from storybard.services.context_assembly import get_campaign_settings

MODEL = "test-model"


class TestGetCampaignSettingsAutoCreates:
    async def test_auto_creates_defaults_for_unknown_campaign(self, db_session):
        campaign_id = uuid.uuid4()
        settings = await get_campaign_settings(db_session, campaign_id=campaign_id)

        assert settings.campaign_id == campaign_id
        assert settings.seed_npc_count == 3
        assert settings.seed_always_faction is True
        assert settings.narration_hard_stagnation_threshold == 5

    async def test_second_call_returns_same_row_not_a_new_one(self, db_session):
        campaign_id = uuid.uuid4()
        first = await get_campaign_settings(db_session, campaign_id=campaign_id)
        first.seed_npc_count = 7
        await db_session.flush()

        second = await get_campaign_settings(db_session, campaign_id=campaign_id)
        assert second.seed_npc_count == 7

        rows = (
            await db_session.execute(select(CampaignSettings).where(CampaignSettings.campaign_id == campaign_id))
        ).scalars().all()
        assert len(rows) == 1


class TestCommitSeedCreatesSettings:
    async def test_seeded_campaign_gets_a_settings_row(self, db_session, lm_client_with):
        llm = lm_client_with({"ops": [], "planted_reveal": None})
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e"))
        result = await commit_seed(db_session, proposal=proposal)

        row = (
            await db_session.execute(
                select(CampaignSettings).where(CampaignSettings.campaign_id == uuid.UUID(result.campaign_id))
            )
        ).scalar_one()
        assert row.seed_npc_count == 3
