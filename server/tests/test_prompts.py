from __future__ import annotations

from storybard.chain.prompts import (
    mechanical_check_prompt,
    memory_regression_prompt,
    narrator_prompt,
    opportunity_spotting_prompt,
    plan_synthesis_prompt,
    plausibility_prompt,
    seed_content_prompt,
    seed_narrative_prompt,
    twist_prompt,
    world_update_prompt,
)


class TestPlanSynthesisPromptSeesThreadsAndScene:
    def test_system_instructs_directors_note_not_prose(self):
        system, user = plan_synthesis_prompt(
            player_text="x", plausibility={}, mechanical_check={}, thread_tick={}, opportunity_spotting={},
            tone={}, campaign_summary="", recent_turns=[], turns_since_thread_activity=0, turn_count=0,
        )
        assert "director's note" in system
        assert "director's note" in user

    def test_active_threads_present_in_user_prompt(self):
        _, user = plan_synthesis_prompt(
            player_text="x", plausibility={}, mechanical_check={}, thread_tick={}, opportunity_spotting={},
            tone={}, campaign_summary="", recent_turns=[], turns_since_thread_activity=0, turn_count=0,
            active_threads=[{"id": "t1", "title": "The Deep Current", "summary": "x", "tier": "major"}],
        )
        assert "The Deep Current" in user

    def test_scene_due_beats_present_in_user_prompt(self):
        _, user = plan_synthesis_prompt(
            player_text="x", plausibility={}, mechanical_check={}, thread_tick={}, opportunity_spotting={},
            tone={}, campaign_summary="", recent_turns=[], turns_since_thread_activity=0, turn_count=0,
            scene={"location_name": "The Drowned Temple", "actors_present": [], "due_beats": [
                {"beat_id": "b1", "thread_title": "The Deep Current", "description": "The creature surfaces."}
            ]},
        )
        assert "The creature surfaces." in user

    def test_absent_when_not_given(self):
        _, user = plan_synthesis_prompt(
            player_text="x", plausibility={}, mechanical_check={}, thread_tick={}, opportunity_spotting={},
            tone={}, campaign_summary="", recent_turns=[], turns_since_thread_activity=0, turn_count=0,
        )
        assert "## Active threads" in user  # section always present, just empty
        assert user.count("[]") >= 1

    def test_actor_context_present_in_user_prompt(self):
        _, user = plan_synthesis_prompt(
            player_text="x", plausibility={}, mechanical_check={}, thread_tick={}, opportunity_spotting={},
            tone={}, campaign_summary="", recent_turns=[], turns_since_thread_activity=0, turn_count=0,
            actor_context={"name": "Mara Vex", "personal_stakes": "Avenge her sister."},
        )
        assert "Mara Vex" in user
        assert "Avenge her sister." in user


class TestTwistPromptSeesActorAndScene:
    def test_actor_context_and_due_beats_present(self):
        _, user = twist_prompt(
            player_text="x", plan="", campaign_summary="", recent_turns=[], active_threads=[],
            actor_context={"name": "Mara Vex"},
            scene={"location_name": "x", "actors_present": [], "due_beats": [
                {"beat_id": "b1", "thread_title": "T", "description": "The bear wakes."}
            ]},
        )
        assert "Mara Vex" in user
        assert "The bear wakes." in user


class TestPlausibilityPromptSeesScene:
    def test_actors_present_shown_when_scene_given(self):
        _, user = plausibility_prompt(
            player_text="x", intent={}, scene_text="", actor_context={}, campaign_summary="",
            recent_turns=[],
            scene={"location_name": "x", "actors_present": [{"id": "1", "name": "Pip"}], "due_beats": []},
        )
        assert "Pip" in user

    def test_no_scene_degrades_gracefully(self):
        _, user = plausibility_prompt(
            player_text="x", intent={}, scene_text="", actor_context={}, campaign_summary="", recent_turns=[],
        )
        assert "Who's actually here" not in user


class TestOpportunitySpottingPromptSeesDueBeats:
    def test_due_beats_shown_when_scene_given(self):
        _, user = opportunity_spotting_prompt(
            player_text="x", plausibility={}, active_threads=[], scene_text="", actor_context={},
            recent_turns=[],
            scene={"location_name": "x", "actors_present": [], "due_beats": [
                {"beat_id": "b1", "thread_title": "T", "description": "The gear hums."}
            ]},
        )
        assert "The gear hums." in user

    def test_system_instructs_preferring_active_threads(self):
        system, _ = plan_synthesis_prompt(
            player_text="x", plausibility={}, mechanical_check={}, thread_tick={}, opportunity_spotting={},
            tone={}, campaign_summary="", recent_turns=[], turns_since_thread_activity=0, turn_count=0,
        )
        assert "active threads" in system.lower()


class TestNarratorPromptSeesThreadsAndBeats:
    def test_active_threads_present(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            active_threads=[{"id": "t1", "title": "The Deep Current", "summary": "x", "tier": "major"}],
        )
        assert "The Deep Current" in user

    def test_due_beat_surfaced_with_instruction_to_weave_in(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            scene={"location_name": "x", "actors_present": [], "due_beats": [
                {"beat_id": "b1", "thread_title": "The Deep Current", "description": "The creature surfaces."}
            ]},
        )
        assert "The creature surfaces." in user
        assert "Planned beats due" in user

    def test_no_beats_section_when_scene_has_none_due(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            scene={"location_name": "x", "actors_present": [], "due_beats": []},
        )
        assert "Planned beats due" not in user


class TestWorldUpdatePromptDescribesBeatOpsAndScene:
    def test_fire_and_abandon_beat_described(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "fire_beat" in user
        assert "abandon_beat" in user
        assert "initial_beats" in user

    def test_scene_content_present_when_given(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
            scene={"location_name": "x", "actors_present": [], "due_beats": [
                {"beat_id": "b1", "thread_title": "T", "description": "Due here."}
            ]},
        )
        assert "Due here." in user

    def test_update_actor_guidance_warns_against_transient_status(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "DURABLE" in user
        assert "transient" in user

    def test_create_and_update_actor_describe_speech_style(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "create_actor(name, kind, bio, current_node_id, current_goal, speech_style)" in user
        assert "update_actor(actor_id, current_goal, bio, speech_style)" in user


class TestWorldUpdatePromptIncludesNarration:
    def test_narration_text_present_in_user_prompt(self):
        _, user = world_update_prompt(
            player_text="I look around.",
            plausibility={},
            mechanical_check={},
            active_threads=[],
            active_clocks=[],
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
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "narration" in system.lower()

    def test_instructs_creating_threads_hooks_from_narration(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "mystery" in user.lower()

    def test_active_clocks_present_and_tick_clock_warns_against_inventing_ids(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[],
            active_clocks=[{"id": "abc-123", "thread_id": "t1", "name": "Countdown", "segments_filled": 1, "segments_total": 4}],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "abc-123" in user
        assert "do not invent" in user.lower()
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

    def test_system_prompt_references_speech_style(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
        )
        assert "speech_style" in system

    def test_system_prompt_explains_present_flag(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
        )
        assert "present=true" in system
        assert "present=false" in system

    def test_system_prompt_forbids_verbatim_plan_copy(self):
        # Live campaign audit caught the Narrator outputting plan_synthesis's text
        # byte-for-byte as "narration" — confirmed via the raw chain trace, not a guess.
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
        )
        assert "verbatim" in system
        assert "director's note" in system

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

    def test_npc_impressions_present_when_given(self):
        _, user = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            npc_impressions=[{"npc_name": "Borin", "text": "Trusts them after the ale house favor."}],
        )
        assert "Borin" in user
        assert "Trusts them" in user

    def test_system_prompt_instructs_distinct_npc_voices(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
        )
        assert "distinct voice" in system


class TestMechanicalCheckPromptIntentAwareness:
    def test_intent_included_in_user_prompt(self):
        _, user = mechanical_check_prompt(
            player_text="ok what is happening", plausibility={}, turn_count=0,
            intent={"primitive": "unknown", "target": None, "notes": []},
        )
        assert "unknown" in user

    def test_system_instructs_no_roll_for_meta_messages(self):
        system, _ = mechanical_check_prompt(player_text="x", plausibility={}, turn_count=0)
        assert "out-of-character" in system.lower() or "meta" in system.lower()

    def test_user_rule_text_references_unknown_primitive(self):
        _, user = mechanical_check_prompt(player_text="x", plausibility={}, turn_count=0)
        assert "unknown" in user


class TestWorldUpdatePromptRollAndConsequenceOps:
    def test_apply_damage_and_apply_condition_ops_described(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "apply_damage" in user
        assert "apply_condition" in user

    def test_roll_result_present_when_given(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
            roll_resolution={"rolled": 3, "modifier": 1, "total": 4, "dc": 15, "ability": "str", "degree": "clean_failure"},
            acting_actor_id="abc-123",
        )
        assert "clean_failure" in user
        assert "abc-123" in user

    def test_roll_result_absent_when_not_given(self):
        _, user = world_update_prompt(
            player_text="x", plausibility={}, mechanical_check={}, active_threads=[], active_clocks=[],
            thread_tick_suggestions=[], hook_ideas=[], known_actors=[], known_locations=[], narration="",
            recent_turns=[],
        )
        assert "Roll result" not in user


class TestNarratorPromptRollTruthfulness:
    def test_system_instructs_truthful_roll_narration_when_roll_given(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            roll_resolution={"rolled": 2, "modifier": 0, "total": 2, "dc": 15, "ability": "str", "degree": "clean_failure"},
        )
        assert "truthfully" in system.lower()

    def test_no_truthfulness_instruction_when_no_roll(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
        )
        assert "truthfully" not in system.lower()


class TestMechanicalDegreesOfSuccess:
    def test_texture_note_present_when_enabled(self):
        _, user = mechanical_check_prompt(player_text="x", plausibility={}, turn_count=0, degrees_of_success=True)
        assert "degrees of success" in user

    def test_texture_note_absent_when_disabled(self):
        _, user = mechanical_check_prompt(player_text="x", plausibility={}, turn_count=0, degrees_of_success=False)
        assert "degrees of success" not in user

    def test_narrator_system_mentions_texture_when_enabled(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            mechanical_texture=True,
        )
        assert "fail-forward" in system

    def test_narrator_system_omits_texture_when_disabled(self):
        system, _ = narrator_prompt(
            player_text="x", plausibility={}, mechanical_check={}, plan="", tone={},
            style_description="", verbosity_words=100.0, scene_text="",
            actor_context={}, recent_turns=[], relevant_memories=[],
            known_actors=[], known_locations=[], recent_world_events=[], campaign_summary="",
            mechanical_texture=False,
        )
        assert "fail-forward" not in system


class TestMemoryRegressionPromptNpcImpressions:
    def test_npc_tracking_section_included_when_enabled(self):
        _, user = memory_regression_prompt(
            player_text="x", narration="x", previous_summary="",
            known_actors=[{"id": "abc-1", "name": "Borin", "kind": "npc"}],
            track_npc_impressions=True,
        )
        assert "abc-1" in user
        assert "npc_impressions" in user

    def test_npc_tracking_section_omitted_when_disabled(self):
        _, user = memory_regression_prompt(
            player_text="x", narration="x", previous_summary="",
            known_actors=[{"id": "abc-1", "name": "Borin", "kind": "npc"}],
            track_npc_impressions=False,
        )
        assert "abc-1" not in user


class TestSeedContentPrompt:
    def test_pushes_mechanical_distinctiveness_not_just_flavor_text(self):
        # Live campaign audit: races/classes had bespoke candy-themed names but generic
        # reskinned +1/immunity mechanics underneath — the user's "kinda random" read.
        _, user = seed_content_prompt(world_description="x", inspiration_tags=[], must_include=[])
        assert "isn't enough on its own" in user
        assert "specific to this world's premise" in user


class TestSeedNarrativePrompt:
    def test_counts_and_flags_reflected(self):
        _, user = seed_narrative_prompt(
            world_name="Oakhaven",
            world_description="A quiet crossroads town.",
            inspiration_tags=[],
            must_include=[],
            npc_count=5,
            hook_count=2,
            rumor_count=4,
            npc_relationships=True,
            location_depth=2,
            include_faction=True,
            include_planted_reveal=True,
            player_actor_name="Arin",
        )
        assert "exactly 5 NPCs" in user
        assert "2 real hooks" in user
        assert "4 rumors" in user
        assert "Oakhaven" in user
        assert "speech_style" in user

    def test_current_node_id_not_hardcoded_to_starting_location(self):
        # Live campaign audit found every seeded NPC pinned to the top-level location
        # regardless of where their own bio said they were (e.g. an NPC whose bio said
        # "operates from the hidden district" still got current_node_id = the kingdom).
        # The instruction used to hardcode "set current_node_id to exactly '{world_name}'"
        # unconditionally; this locks in that it no longer does.
        _, user = seed_narrative_prompt(
            world_name="Oakhaven", world_description="x", inspiration_tags=[], must_include=[],
            npc_count=1, hook_count=1, rumor_count=1, npc_relationships=False,
            location_depth=2, include_faction=False, include_planted_reveal=False,
            player_actor_name="Arin",
        )
        assert "set current_node_id to exactly 'Oakhaven'" not in user
        assert "whichever location this character is actually described as being at" in user

    def test_thread_variety_instruction_present_with_multiple_must_includes(self):
        _, user = seed_narrative_prompt(
            world_name="Oakhaven", world_description="x", inspiration_tags=[],
            must_include=["A cursed relic", "A rival duke"],
            npc_count=1, hook_count=1, rumor_count=1, npc_relationships=False,
            location_depth=1, include_faction=False, include_planted_reveal=False,
            player_actor_name="Arin",
        )
        assert "genuinely distinct from each other" in user

    def test_faction_and_location_and_reveal_omitted_when_disabled(self):
        _, user = seed_narrative_prompt(
            world_name="Oakhaven",
            world_description="A quiet crossroads town.",
            inspiration_tags=[],
            must_include=[],
            npc_count=1,
            hook_count=1,
            rumor_count=1,
            npc_relationships=False,
            location_depth=1,
            include_faction=False,
            include_planted_reveal=False,
            player_actor_name="Arin",
        )
        assert "Do not propose a faction" in user
        assert "Do not propose any locations" in user
        assert "Set planted_reveal to null" in user

    def test_must_include_elaboration_instruction_present_when_given(self):
        _, user = seed_narrative_prompt(
            world_name="Oakhaven", world_description="x", inspiration_tags=[],
            must_include=["A cursed relic", "A rival duke"],
            npc_count=1, hook_count=1, rumor_count=1, npc_relationships=True,
            location_depth=1, include_faction=False, include_planted_reveal=False,
            player_actor_name="Arin",
        )
        assert "never copy the wish text verbatim" in user
        assert "initial_beats" in user
        assert "create_major_thread(title, summary" in user

    def test_warns_against_reusing_player_name_for_an_npc(self):
        # Live audit caught a seeded NPC named identically to the player character — the
        # Narrator then described the same name as both "you" and a separate NPC in the
        # same scene. seed_narrative_prompt never received the player's name at all.
        _, user = seed_narrative_prompt(
            world_name="Oakhaven", world_description="x", inspiration_tags=[], must_include=[],
            npc_count=1, hook_count=1, rumor_count=1, npc_relationships=False,
            location_depth=1, include_faction=False, include_planted_reveal=False,
            player_actor_name="Elias Thorne",
        )
        assert "Elias Thorne" in user
        assert "do not reuse it for any NPC" in user

    def test_must_include_elaboration_instruction_absent_when_empty(self):
        _, user = seed_narrative_prompt(
            world_name="Oakhaven", world_description="x", inspiration_tags=[], must_include=[],
            npc_count=1, hook_count=1, rumor_count=1, npc_relationships=True,
            location_depth=1, include_faction=False, include_planted_reveal=False,
            player_actor_name="Arin",
        )
        assert "never copy the wish text verbatim" not in user
