from __future__ import annotations

from storybard.chain.prompts import narrator_prompt, world_update_prompt


class TestWorldUpdatePromptIncludesNarration:
    def test_narration_text_present_in_user_prompt(self):
        _, user = world_update_prompt(
            player_text="I look around.",
            plausibility={},
            mechanical_check={},
            active_threads=[],
            thread_tick_suggestions=[],
            hook_ideas=[],
            known_actors=[],
            known_locations=[],
            narration="A figure emerges from the shadows, draped in silk.",
            recent_turns=[],
        )
        assert "A figure emerges from the shadows, draped in silk." in user

    def test_instructs_creating_entities_introduced_in_narration(self):
        system, _ = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "narration" in system.lower()

    def test_instructs_creating_threads_hooks_from_narration(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "mystery" in user.lower()
        assert "unresolved tension worth remembering" in user.lower()


class TestNarratorPromptKnownEntitiesAndDialogue:
    def test_known_actors_and_locations_present(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[{"id": "1", "name": "Borin", "kind": "npc"}],
            known_locations=[{"id": "2", "name": "Oakhaven"}],
            recent_world_events=[], campaign_summary="",
        )
        assert "Borin" in user
        assert "Oakhaven" in user

    def test_system_prompt_instructs_direct_dialogue(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
        )
        assert "quotation marks" in system

    def test_recent_world_events_present(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[],
            recent_world_events=[{"op": "tick_clock", "reason": "ticked", "entity_id": "1"}],
            campaign_summary="",
        )
        assert "tick_clock" in user

    def test_campaign_summary_present(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[],
            campaign_summary="The party has uncovered a plot against the duke.",
        )
        assert "plot against the duke" in user
