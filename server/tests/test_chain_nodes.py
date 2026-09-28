from __future__ import annotations

import pytest

from storybard.chain.graph import (
    intent_generate,
    mechanical_check_generate,
    narrator_generate,
    plausibility_generate,
)
from storybard.services.llm.lmstudio_client import LMStudioError

MODEL = "test-model"


class TestIntentGenerate:
    async def test_valid_response(self, lm_client_with):
        llm = lm_client_with({"primitive": "speak", "target": "Borin", "notes": []})
        result = await intent_generate({"player_text": "I talk to Borin", "mode": "explore"}, llm=llm, model=MODEL)
        assert result["_proposed_intent"]["primitive"] == "speak"
        assert result["_proposed_intent"]["target"] == "Borin"

    async def test_malformed_json_fails_loudly(self, lm_client_malformed):
        llm = lm_client_malformed()
        with pytest.raises(LMStudioError):
            await intent_generate({"player_text": "I talk to Borin", "mode": "explore"}, llm=llm, model=MODEL)


class TestPlausibilityGenerate:
    async def test_valid_response(self, lm_client_with):
        llm = lm_client_with(
            {"feasibility": "feasible", "reason": "Nothing stops this.", "twist": None, "time_passed": "a minute"}
        )
        result = await plausibility_generate(
            {"player_text": "I walk into the inn", "intent": {}, "scene_text": ""}, llm=llm, model=MODEL
        )
        assert result["_proposed_plausibility"]["feasibility"] == "feasible"
        assert result["_proposed_plausibility"]["time_passed"] == "a minute"

    async def test_missing_required_field_fails_loudly(self, lm_client_with):
        # Valid JSON, but missing the required `reason` field — the exact bug class that
        # bit v1 twice (a shape that's syntactically fine but doesn't match the contract).
        llm = lm_client_with({"feasibility": "feasible"})
        with pytest.raises(LMStudioError):
            await plausibility_generate(
                {"player_text": "x", "intent": {}, "scene_text": ""}, llm=llm, model=MODEL
            )


class TestMechanicalCheckGenerate:
    async def test_valid_response(self, lm_client_with):
        llm = lm_client_with({"roll_required": True, "skill": "persuasion", "dc": 15, "reason": "Uncertain."})
        result = await mechanical_check_generate(
            {"player_text": "I persuade the guard", "plausibility": {}}, llm=llm, model=MODEL
        )
        assert result["_proposed_mechanical_check"]["roll_required"] is True
        assert result["_proposed_mechanical_check"]["dc"] == 15


class TestNarratorGenerate:
    async def test_valid_response(self, lm_client_with):
        llm = lm_client_with({"narration": "The door creaks open."})
        result = await narrator_generate(
            {
                "player_text": "I open the door",
                "plausibility": {},
                "mechanical_check": {},
                "style_description": "terse",
                "verbosity_words": 100,
            },
            llm=llm,
            model=MODEL,
        )
        assert result["_proposed_narration"]["narration"] == "The door creaks open."

    async def test_wrong_field_name_fails_loudly(self, lm_client_with):
        # e.g. the model emits `text` instead of `narration` — same failure mode as v1's
        # update_story_thread "changes" wrapper bug. Must fail, not silently no-op.
        llm = lm_client_with({"text": "The door creaks open."})
        with pytest.raises(LMStudioError):
            await narrator_generate(
                {
                    "player_text": "I open the door",
                    "plausibility": {},
                    "mechanical_check": {},
                    "style_description": "terse",
                    "verbosity_words": 100,
                },
                llm=llm,
                model=MODEL,
            )
