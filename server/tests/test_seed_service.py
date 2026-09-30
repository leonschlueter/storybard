from __future__ import annotations

import uuid

from sqlalchemy import select

from storybard.chain.ops import SeedContentOut, SeedNarrativeOut
from storybard.chain.seed_service import SeedInput, commit_seed, propose_seed
from storybard.core.config import settings
from storybard.domain.actor import Actor, CharacterSheet
from storybard.domain.campaign import Campaign
from storybard.domain.campaign_settings import CampaignSettings
from storybard.domain.faction import Faction
from storybard.domain.hook import Hook
from storybard.domain.inventory import InventoryItem
from storybard.domain.item import ItemDef
from storybard.domain.reveal import PlantedReveal
from storybard.domain.ruleset import AncestryDef, AttributeDefinition, ClassDef
from storybard.domain.spell import SpellDef
from storybard.domain.thread import Thread
from storybard.domain.thread_beat import ThreadBeat
from storybard.domain.world import WorldNode

MODEL = "test-model"

EMPTY_NARRATIVE = {"ops": [], "planted_reveal": None}


class TestProposeSeedStandard5e:
    async def test_mechanical_ops_present_with_no_extra_llm_call(self, lm_client_with):
        # Only the narrative call should hit the LLM in standard_5e mode — mechanical
        # content (ancestries/classes/items/spells) is built from constants, no call
        # needed. lm_client_with's structured_chat ignores which prompt it was called
        # with, so this doesn't distinguish "0 calls" from "1 call" directly, but it does
        # prove standard_5e mode doesn't need SeedContentOut at all (no error validating
        # against the wrong schema).
        llm = lm_client_with(EMPTY_NARRATIVE)
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e")
        )
        op_types = [op["op"] for op in proposal.ops]
        assert op_types.count("create_ancestry_def") == 4
        assert op_types.count("create_class_def") == 4
        assert op_types.count("create_item_def") == 5
        assert op_types.count("create_spell_def") == 4
        assert op_types.count("create_world_node") == 1

    async def test_must_include_elaborated_by_narrative_call_not_copied_verbatim(self, lm_client_with):
        # Real bug fixed here: must_include threads used to be constructed directly in
        # Python (title=wish, summary=wish, no beats) — flat and un-elaborated. They now
        # come from the narrative LLM call, which is expected to give each a real title
        # distinct from its summary, plus staged beats.
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_major_thread", "title": "The Duke's Hidden Blade", "owner_type": "campaign",
                        "owner_id": None, "summary": "Duke Halric secretly plots against the crown.",
                        "initial_beats": [{"description": "A courier is intercepted.", "location_id": None}],
                    },
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(
            llm=llm,
            model=MODEL,
            seed_input=SeedInput(races_classes_mode="standard_5e", must_include=["A rival duke"]),
        )
        thread_ops = [op for op in proposal.ops if op["op"] == "create_major_thread"]
        assert len(thread_ops) == 1
        assert thread_ops[0]["title"] != thread_ops[0]["summary"]
        assert len(thread_ops[0]["initial_beats"]) == 1

    async def test_seeding_settings_forwarded_to_proposal(self, lm_client_with):
        llm = lm_client_with(EMPTY_NARRATIVE)
        proposal = await propose_seed(
            llm=llm,
            model=MODEL,
            seed_input=SeedInput(races_classes_mode="standard_5e", seed_npc_count=7, seed_always_faction=False),
        )
        assert proposal.settings["seed_npc_count"] == 7
        assert proposal.settings["seed_always_faction"] is False


class TestProposeSeedGenerate:
    async def test_generate_mode_uses_llm_for_both_calls(self, lm_client_by_model):
        llm = lm_client_by_model(
            {
                "SeedContentOut": {
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
                },
                "SeedNarrativeOut": EMPTY_NARRATIVE,
            }
        )
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="generate")
        )
        op_types = [op["op"] for op in proposal.ops]
        assert "create_ancestry_def" in op_types
        assert "create_class_def" in op_types

    async def test_retries_once_when_first_pass_omits_a_category(self):
        """Real failure observed live: generate mode proposed 4 ancestries and nothing
        else (zero classes/items/spells) — Party Creation was unusable, and the player
        hit a confusing 404 trying to confirm with no class selected. _generate_mechanical_
        content should retry once and use whichever pass is actually complete."""
        from storybard.chain.ops import CreateAncestryDefOp, CreateClassDefOp, CreateItemDefOp, CreateSpellDefOp

        incomplete = SeedContentOut(
            ops=[CreateAncestryDefOp(op="create_ancestry_def", key="a1", name="A", description=None, speed=30, features={})]
        )
        complete = SeedContentOut(
            ops=[
                CreateAncestryDefOp(op="create_ancestry_def", key="a1", name="A", description=None, speed=30, features={}),
                CreateClassDefOp(
                    op="create_class_def", key="c1", name="C", description=None, hit_die=8,
                    primary_attribute_key="str", proficiencies={}, spellcasting=False, starting_equipment={},
                ),
                CreateItemDefOp(op="create_item_def", key="i1", name="I", description=None, item_type="gear", properties={}),
                CreateSpellDefOp(
                    op="create_spell_def", name="S", description=None, level=1, school="x",
                    casting_time="1 action", range="x", duration="x", effect="x",
                ),
            ]
        )
        calls = {"n": 0}

        async def fake_structured_chat(*, model, system, user, output_model, temperature=0.2):
            if output_model.__name__ == "SeedContentOut":
                calls["n"] += 1
                return incomplete if calls["n"] == 1 else complete
            return SeedNarrativeOut.model_validate(EMPTY_NARRATIVE)

        class _FakeLLM:
            structured_chat = staticmethod(fake_structured_chat)

        proposal = await propose_seed(llm=_FakeLLM(), model=MODEL, seed_input=SeedInput(races_classes_mode="generate"))
        op_types = {op["op"] for op in proposal.ops}
        assert calls["n"] == 2
        assert {"create_ancestry_def", "create_class_def", "create_item_def", "create_spell_def"} <= op_types
        assert "create_world_node" in op_types


class TestProposeSeedNarrativeContent:
    async def test_npc_and_hook_ops_flow_into_proposal(self, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_actor", "name": "Borin", "kind": "npc", "bio": "Runs the inn.",
                        "current_node_id": "Oakhaven", "current_goal": "Pay off a debt.",
                        "speech_style": "Gruff, short sentences.",
                    },
                    {"op": "propose_hook", "origin": "seed", "proposed_text": "A stranger arrives.", "touches_entity_id": None},
                    {"op": "propose_hook", "origin": "rumor", "proposed_text": "The well is cursed.", "touches_entity_id": None},
                ],
                "planted_reveal": "Borin secretly works for the rival duke.",
            }
        )
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(world_name="Oakhaven"))
        op_types = [op["op"] for op in proposal.ops]
        assert op_types.count("create_actor") == 1
        assert op_types.count("propose_hook") == 2
        assert proposal.planted_reveal == "Borin secretly works for the rival duke."

    async def test_planted_reveal_dropped_when_setting_off(self, lm_client_with):
        llm = lm_client_with({"ops": [], "planted_reveal": "A secret anyway."})
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(seed_planted_reveal=False)
        )
        assert proposal.planted_reveal is None


class TestCommitSeed:
    async def test_commit_creates_all_entities(self, db_session, lm_client_with):
        llm = lm_client_with(EMPTY_NARRATIVE)
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e", campaign_name="Test World")
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

        campaign_settings = (
            await db_session.execute(select(CampaignSettings).where(CampaignSettings.campaign_id == campaign.id))
        ).scalar_one()
        assert campaign_settings.seed_npc_count == 3

    async def test_narrative_threads_beyond_cap_partially_rejected(self, db_session, lm_client_with):
        # The major-thread cap (chain/ops.py::_create_major_thread) applies uniformly
        # regardless of where a create_major_thread op came from — still enforced even
        # though must_include threads now flow through the narrative LLM call.
        n = settings.MAX_MAJOR_THREADS + 2
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_major_thread", "title": f"Thread {i}", "owner_type": "campaign",
                        "owner_id": None, "summary": f"Summary {i}", "initial_beats": [],
                    }
                    for i in range(n)
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(
            llm=llm, model=MODEL,
            seed_input=SeedInput(races_classes_mode="standard_5e", must_include=[f"wish {i}" for i in range(n)]),
        )
        result = await commit_seed(db_session, proposal=proposal)

        thread_results = [r for r in result.applied_results if r["op"] == "create_major_thread"]
        assert len(thread_results) == n
        assert sum(1 for r in thread_results if r["applied"]) == settings.MAX_MAJOR_THREADS
        assert sum(1 for r in thread_results if not r["applied"]) == 2

        threads = (
            await db_session.execute(select(Thread).where(Thread.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert len(threads) == settings.MAX_MAJOR_THREADS

    async def test_narrative_thread_beats_committed(self, db_session, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_major_thread", "title": "The Duke's Hidden Blade", "owner_type": "campaign",
                        "owner_id": None, "summary": "Duke Halric secretly plots against the crown.",
                        "initial_beats": [
                            {"description": "A courier is intercepted.", "location_id": None},
                            {"description": "The duke's seal turns up on a forged letter.", "location_id": None},
                        ],
                    },
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e", must_include=["A rival duke"])
        )
        result = await commit_seed(db_session, proposal=proposal)

        thread = (
            await db_session.execute(select(Thread).where(Thread.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalar_one()
        beats = (await db_session.execute(select(ThreadBeat).where(ThreadBeat.thread_id == thread.id))).scalars().all()
        assert len(beats) == 2
        assert thread.title != thread.summary

    async def test_narrative_faction_created(self, db_session, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_faction", "name": "The Ashen Circle", "description": None,
                        "goals": {}, "reputation_baseline": 0,
                    }
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(races_classes_mode="standard_5e"))
        result = await commit_seed(db_session, proposal=proposal)

        factions = (
            await db_session.execute(select(Faction).where(Faction.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert len(factions) == 1
        assert factions[0].name == "The Ashen Circle"

    async def test_seeded_npc_and_hooks_committed(self, db_session, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_actor", "name": "Borin", "kind": "npc", "bio": "Runs the inn.",
                        "current_node_id": "Oakhaven", "current_goal": "Pay off a debt.",
                        "speech_style": "Gruff, short sentences.",
                    },
                    {"op": "propose_hook", "origin": "seed", "proposed_text": "A stranger arrives.", "touches_entity_id": None},
                    {"op": "propose_hook", "origin": "rumor", "proposed_text": "The well is cursed.", "touches_entity_id": None},
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(world_name="Oakhaven"))
        result = await commit_seed(db_session, proposal=proposal)

        npcs = (
            await db_session.execute(
                select(Actor).where(Actor.campaign_id == uuid.UUID(result.campaign_id), Actor.kind == "npc")
            )
        ).scalars().all()
        assert len(npcs) == 1
        # current_node_id was the "Oakhaven" name placeholder — resolved to the real root id.
        assert str(npcs[0].current_node_id) == result.world_node_id

        hooks = (
            await db_session.execute(select(Hook).where(Hook.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert {h.origin for h in hooks} == {"seed", "rumor"}

    async def test_npc_colliding_with_player_name_is_rejected_not_created(self, db_session, lm_client_with):
        # Live audit: a seeded NPC named identically to the player character produced a
        # Narrator that described the same name as both "you" and a separate NPC in the
        # same scene. seed_narrative_prompt is now told not to do this, but commit_seed
        # itself must not trust that — this is the code-level backstop.
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_actor", "name": "Arin", "kind": "npc", "bio": "A shady figure.",
                        "current_node_id": "Oakhaven", "current_goal": None, "speech_style": None,
                    },
                    {
                        "op": "create_actor", "name": "Borin", "kind": "npc", "bio": "Runs the inn.",
                        "current_node_id": "Oakhaven", "current_goal": None, "speech_style": None,
                    },
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(
            llm=llm, model=MODEL, seed_input=SeedInput(world_name="Oakhaven", player_actor_name="Arin")
        )
        result = await commit_seed(db_session, proposal=proposal)

        npcs = (
            await db_session.execute(
                select(Actor).where(Actor.campaign_id == uuid.UUID(result.campaign_id), Actor.kind == "npc")
            )
        ).scalars().all()
        assert [n.name for n in npcs] == ["Borin"]
        collision_result = next(r for r in result.applied_results if r.get("reason", "").startswith("name 'Arin'"))
        assert collision_result["applied"] is False

    async def test_child_locations_resolve_name_placeholder_parent(self, db_session, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_world_node", "name": "The Rusty Anchor", "description": "A tavern.",
                        "parent_node_id": "Oakhaven", "scale": "landmark", "x": None, "y": None,
                    },
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(world_name="Oakhaven"))
        result = await commit_seed(db_session, proposal=proposal)

        nodes = (
            await db_session.execute(select(WorldNode).where(WorldNode.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert len(nodes) == 2
        child = next(n for n in nodes if n.name == "The Rusty Anchor")
        assert str(child.parent_node_id) == result.world_node_id
        assert child.depth == 1

    async def test_unresolvable_parent_name_rejected_not_silently_dropped(self, db_session, lm_client_with):
        llm = lm_client_with(
            {
                "ops": [
                    {
                        "op": "create_world_node", "name": "Somewhere", "description": None,
                        "parent_node_id": "A Place That Was Never Seeded", "scale": None, "x": None, "y": None,
                    },
                ],
                "planted_reveal": None,
            }
        )
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput(world_name="Oakhaven"))
        result = await commit_seed(db_session, proposal=proposal)

        rejected = [r for r in result.applied_results if r["op"] == "create_world_node" and not r["applied"]]
        assert any("not found" in r["reason"] for r in rejected)

    async def test_planted_reveal_stored(self, db_session, lm_client_with):
        llm = lm_client_with({"ops": [], "planted_reveal": "Borin secretly works for the rival duke."})
        proposal = await propose_seed(llm=llm, model=MODEL, seed_input=SeedInput())
        result = await commit_seed(db_session, proposal=proposal)

        reveals = (
            await db_session.execute(select(PlantedReveal).where(PlantedReveal.campaign_id == uuid.UUID(result.campaign_id)))
        ).scalars().all()
        assert len(reveals) == 1
        assert reveals[0].secret_text == "Borin secretly works for the rival duke."

    async def test_starting_inventory_created_for_player(self, db_session, lm_client_with):
        llm = lm_client_with(EMPTY_NARRATIVE)
        proposal = await propose_seed(
            llm=llm,
            model=MODEL,
            seed_input=SeedInput(races_classes_mode="standard_5e", seed_starting_inventory_count=2),
        )
        result = await commit_seed(db_session, proposal=proposal)

        rows = (
            await db_session.execute(
                select(InventoryItem).where(InventoryItem.owner_actor_id == uuid.UUID(result.player_actor_id))
            )
        ).scalars().all()
        assert len(rows) == 2

    async def test_starting_inventory_skipped_when_setting_off(self, db_session, lm_client_with):
        llm = lm_client_with(EMPTY_NARRATIVE)
        proposal = await propose_seed(
            llm=llm,
            model=MODEL,
            seed_input=SeedInput(races_classes_mode="standard_5e", seed_starting_inventory=False),
        )
        result = await commit_seed(db_session, proposal=proposal)

        rows = (
            await db_session.execute(
                select(InventoryItem).where(InventoryItem.owner_actor_id == uuid.UUID(result.player_actor_id))
            )
        ).scalars().all()
        assert rows == []

    async def test_session_zero_and_calendar_context_stored(self, db_session, lm_client_with):
        llm = lm_client_with(EMPTY_NARRATIVE)
        proposal = await propose_seed(
            llm=llm,
            model=MODEL,
            seed_input=SeedInput(
                safety_tools="Lines and veils apply.",
                personal_stakes="Your sister went missing here.",
                calendar_context="Early winter, three days before the harvest festival.",
            ),
        )
        result = await commit_seed(db_session, proposal=proposal)

        campaign = await db_session.get(Campaign, uuid.UUID(result.campaign_id))
        assert campaign.safety_tools == "Lines and veils apply."
        assert campaign.personal_stakes == "Your sister went missing here."
        assert campaign.calendar_context == "Early winter, three days before the harvest festival."
