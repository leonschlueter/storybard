from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from storybard.api.party import FinalizeCharacterIn, _finalize_character
from storybard.chain.seed_service import SeedInput, commit_seed, propose_seed
from storybard.domain.actor import CharacterSheet
from sqlalchemy import select

MODEL = "test-model"


async def _seed_campaign(db_session, lm_client_with):
    # propose_seed always makes a narrative-content call now (NPCs/hooks/rumors, feature
    # #1) — a canned empty response is enough for these party-creation tests, which don't
    # care about seeded narrative content.
    llm = lm_client_with({"ops": [], "planted_reveal": None})
    proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e"))
    return await commit_seed(db_session, proposal=proposal)


class TestFinalizeCharacter:
    async def test_roll_method_updates_sheet(self, db_session, lm_client_with):
        result = await _seed_campaign(db_session, lm_client_with)
        sheet = await _finalize_character(
            db_session,
            campaign_id=uuid.UUID(result.campaign_id),
            actor_id=uuid.UUID(result.player_actor_id),
            body=FinalizeCharacterIn(
                ancestry_key="elf",
                class_key="wizard",
                method="roll",
                ability_scores={"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 10, "cha": 10},
            ),
        )
        assert sheet.ancestry == "Elf"
        assert sheet.character_class == "Wizard"
        assert sheet.ability_scores["int"] == 16
        # wizard hit_die=6, con=12 -> mod +1 -> max_hp = 7
        assert sheet.max_hp == 7
        assert sheet.current_hp == 7
        # dex=14 -> mod +2 -> AC = 12
        assert sheet.armor_class == 12
        # elf speed = 30
        assert sheet.speed == 30

    async def test_point_buy_within_budget_succeeds(self, db_session, lm_client_with):
        result = await _seed_campaign(db_session, lm_client_with)
        sheet = await _finalize_character(
            db_session,
            campaign_id=uuid.UUID(result.campaign_id),
            actor_id=uuid.UUID(result.player_actor_id),
            body=FinalizeCharacterIn(
                ancestry_key="human",
                class_key="fighter",
                method="point_buy",
                ability_scores={"str": 15, "dex": 14, "con": 13, "int": 8, "wis": 10, "cha": 8},
            ),
        )
        assert sheet.character_class == "Fighter"

    async def test_point_buy_over_budget_rejected_without_mutating(self, db_session, lm_client_with):
        result = await _seed_campaign(db_session, lm_client_with)
        actor_id = uuid.UUID(result.player_actor_id)
        with pytest.raises(HTTPException) as exc_info:
            await _finalize_character(
                db_session,
                campaign_id=uuid.UUID(result.campaign_id),
                actor_id=actor_id,
                body=FinalizeCharacterIn(
                    ancestry_key="human",
                    class_key="fighter",
                    method="point_buy",
                    ability_scores={"str": 15, "dex": 15, "con": 15, "int": 15, "wis": 15, "cha": 15},
                ),
            )
        assert exc_info.value.status_code == 400

        sheet = (
            await db_session.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id))
        ).scalar_one()
        assert sheet.ancestry is None
        assert sheet.ability_scores == {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

    async def test_out_of_range_point_buy_score_rejected(self, db_session, lm_client_with):
        result = await _seed_campaign(db_session, lm_client_with)
        with pytest.raises(HTTPException) as exc_info:
            await _finalize_character(
                db_session,
                campaign_id=uuid.UUID(result.campaign_id),
                actor_id=uuid.UUID(result.player_actor_id),
                body=FinalizeCharacterIn(
                    ancestry_key="human",
                    class_key="fighter",
                    method="point_buy",
                    ability_scores={"str": 18, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8},
                ),
            )
        assert exc_info.value.status_code == 400

    async def test_unknown_ancestry_key_404s(self, db_session, lm_client_with):
        result = await _seed_campaign(db_session, lm_client_with)
        with pytest.raises(HTTPException) as exc_info:
            await _finalize_character(
                db_session,
                campaign_id=uuid.UUID(result.campaign_id),
                actor_id=uuid.UUID(result.player_actor_id),
                body=FinalizeCharacterIn(
                    ancestry_key="not-a-real-ancestry",
                    class_key="fighter",
                    method="roll",
                    ability_scores={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
                ),
            )
        assert exc_info.value.status_code == 404
