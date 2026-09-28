from __future__ import annotations

import uuid

from sqlalchemy import select

from storybard.chain.seed_service import SeedInput, commit_seed, propose_seed
from storybard.core.config import settings
from storybard.domain.actor import Actor, CharacterSheet
from storybard.domain.campaign import Campaign
from storybard.domain.faction import Faction
from storybard.domain.item import ItemDef
from storybard.domain.ruleset import AncestryDef, AttributeDefinition, ClassDef
from storybard.domain.spell import SpellDef
from storybard.domain.thread import Thread
from storybard.domain.world import WorldNode

MODEL = "test-model"


class TestProposeSeedStandard5e:
    async def test_no_llm_call_needed(self):
        # No lm_client fixture passed at all — if propose_seed tried to call the LLM in
        # standard_5e mode, this test would error on the missing argument, not just be slow.
        proposal = await propose_seed(
            llm=None, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e")
        )
        op_types = [op["op"] for op in proposal.ops]
        assert op_types.count("create_ancestry_def") == 4
        assert op_types.count("create_class_def") == 4
        assert op_types.count("create_item_def") == 5
        assert op_types.count("create_spell_def") == 4
        assert op_types.count("create_world_node") == 1

    async def test_must_include_becomes_major_thread_ops(self):
        proposal = await propose_seed(
            llm=None,
            model=MODEL,
            seed_input=SeedInput(races_classes_mode="standard_5e", must_include=["A cursed relic", "A rival duke"]),
        )
        thread_ops = [op for op in proposal.ops if op["op"] == "create_major_thread"]
        assert len(thread_ops) == 2
        assert {t["title"] for t in thread_ops} == {"A cursed relic", "A rival duke"}


class TestProposeSeedGenerate:
    async def test_generate_mode_uses_llm(self, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_ancestry_def", "key": "elf", "name": "Elf", "description": None,
                        "speed": 30, "features": {},
                    },
                    {
                        "op": "create_class_def", "key": "wizard", "name": "Wizard", "description": None,
                        "hit_die": 6, "primary_attribute_key": "int", "proficiencies": {},
                        "spellcasting": True, "starting_equipment": {},
                    },
                ]
            }
        )
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="generate")
        )
        op_types = [op["op"] for op in proposal.ops]
        assert "create_ancestry_def" in op_types
        assert "create_class_def" in op_types
        assert "create_world_node" in op_types


class TestCommitSeed:
    async def test_commit_creates_all_entities(self, db_session):
        proposal = await propose_seed(
            llm=None, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e", campaign_name="Test World")
        )
        result = await commit_seed(db_session, proposal=proposal)

        campaign = await db_session.get(Campaign, uuid.UUID(result.campaign_id))
        assert campaign.name == "Test World"

        attrs = (
            await db_session.execute(select(AttributeDefinition).where(AttributeDefinition.campaign_id == campaign.id))
        ).scalars().all()
        assert len(attrs) == 6

        ancestries = (
            await db_session.execute(select(AncestryDef).where(AncestryDef.campaign_id == campaign.id))
        ).scalars().all()
        assert len(ancestries) == 4

        classes = (
            await db_session.execute(select(ClassDef).where(ClassDef.campaign_id == campaign.id))
        ).scalars().all()
        assert len(classes) == 4

        items = (await db_session.execute(select(ItemDef).where(ItemDef.campaign_id == campaign.id))).scalars().all()
        assert len(items) == 5

        spells = (
            await db_session.execute(select(SpellDef).where(SpellDef.campaign_id == campaign.id))
        ).scalars().all()
        assert len(spells) == 4

        nodes = (await db_session.execute(select(WorldNode).where(WorldNode.campaign_id == campaign.id))).scalars().all()
        assert len(nodes) == 1

        player = await db_session.get(Actor, uuid.UUID(result.player_actor_id))
        assert player.kind == "player"
        assert str(player.current_node_id) == result.world_node_id

        sheet = (
            await db_session.execute(select(CharacterSheet).where(CharacterSheet.actor_id == player.id))
        ).scalar_one()
        assert sheet.ability_scores == {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

    async def test_wishlist_longer_than_thread_cap_partially_rejected(self, db_session):
        wishes = [f"Plot hook {i}" for i in range(settings.MAX_MAJOR_THREADS + 2)]
        proposal = await propose_seed(
            llm=None, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e", must_include=wishes)
        )
        result = await commit_seed(db_session, proposal=proposal)

        thread_results = [r for r in result.applied_results if r["op"] == "create_major_thread"]
        assert len(thread_results) == len(wishes)
        assert sum(1 for r in thread_results if r["applied"]) == settings.MAX_MAJOR_THREADS
        assert sum(1 for r in thread_results if not r["applied"]) == 2

        threads = (
            await db_session.execute(select(Thread).where(Thread.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert len(threads) == settings.MAX_MAJOR_THREADS

    async def test_generate_mode_faction_created(self, db_session, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_faction", "name": "The Ashen Circle", "description": None,
                        "goals": {}, "reputation_baseline": 0,
                    }
                ]
            }
        )
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="generate"))
        result = await commit_seed(db_session, proposal=proposal)

        factions = (
            await db_session.execute(select(Faction).where(Faction.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert len(factions) == 1
        assert factions[0].name == "The Ashen Circle"
