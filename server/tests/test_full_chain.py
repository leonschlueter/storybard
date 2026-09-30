from __future__ import annotations

import uuid

from storybard.chain.graph import build_graph
from storybard.chain.service import advance_turn, resolve_step
from storybard.domain.actor import Actor
from storybard.domain.chain_trace import TurnRun

CANNED_RESPONSES = {
    "IntentOut": {"primitive": "move", "target": "town", "notes": []},
    "PlausibilityOut": {"feasibility": "feasible", "reason": "fine", "twist": None, "time_passed": "a moment"},
    "ThreadTickOut": {"tick_suggestions": []},
    "OpportunitySpottingOut": {"hook_ideas": []},
    "MechanicalCheckOut": {"roll_required": False, "skill": None, "dc": None, "reason": "no risk"},
    "ToneAssessmentOut": {"tension": "calm", "drivers": []},
    "PlanSynthesisOut": {"plan": "Describe the town."},
    "TwistOut": {"complication": "A guard recognizes you from a wanted poster."},
    "WorldUpdateOut": {"ops": []},
    "NarratorOut": {"narration": "You walk into town."},
    "CreateMemoryOut": {
        "memories": [{"title": "Arrived in town", "text": "I arrived in town.", "importance": 2}],
        "campaign_summary_update": "The party has just arrived in town.",
        "npc_impressions": [],
    },
}

EXPECTED_NODE_ORDER = [
    "intent_parse",
    "plausibility_check",
    "thread_tick",
    "opportunity_spotting",
    "mechanical_check",
    "tone_assessment",
    "plan_synthesis",
    "narrator",
    "world_update",
    "memory_regression",
]


async def test_full_chain_completes_in_order_and_persists(db_session, lm_client_by_model):
    llm = lm_client_by_model(CANNED_RESPONSES)
    runtime = build_graph(llm=llm, model="test-model", creative_model="test-model")

    campaign_id = uuid.uuid4()
    actor = Actor(campaign_id=campaign_id, name="Arin", kind="player")
    db_session.add(actor)
    await db_session.flush()

    turn_run = TurnRun(campaign_id=campaign_id, actor_id=actor.id, action_text="I walk into town.")
    db_session.add(turn_run)
    await db_session.flush()

    initial_state = {
        "player_text": "I walk into town.",
        "mode": "explore",
        "scene_text": "",
        "style_description": "",
        "verbosity_words": 150.0,
        "active_threads": [],
        "active_clocks": [],
        "previous_tone": {},
    }

    result = await advance_turn(runtime=runtime, db=db_session, turn_run=turn_run, resume_or_initial=initial_state)

    seen_order = []
    while result["status"] == "paused":
        step = result["step"]
        seen_order.append(step.node_type)
        result = await resolve_step(
            runtime=runtime, db=db_session, step=step, turn_run=turn_run, action="approve", edited_output=None
        )

    assert seen_order == EXPECTED_NODE_ORDER
    assert result["status"] == "completed"
    assert result["turn_run"].final_narration == "You walk into town."


async def _run_full_turn(
    db_session, lm_client_by_model, *, extra_state: dict, responses: dict | None = None
) -> tuple[list[str], dict]:
    """Returns (seen_order, steps_by_type) — steps_by_type lets callers inspect a specific
    paused step's raw_output, not just the ordering."""
    llm = lm_client_by_model(responses or CANNED_RESPONSES)
    runtime = build_graph(llm=llm, model="test-model", creative_model="test-model")

    campaign_id = uuid.uuid4()
    actor = Actor(campaign_id=campaign_id, name="Arin", kind="player")
    db_session.add(actor)
    await db_session.flush()

    turn_run = TurnRun(campaign_id=campaign_id, actor_id=actor.id, action_text="I walk into town.")
    db_session.add(turn_run)
    await db_session.flush()

    initial_state = {
        "player_text": "I walk into town.",
        "mode": "explore",
        "scene_text": "",
        "style_description": "",
        "verbosity_words": 150.0,
        "active_threads": [],
        "active_clocks": [],
        "previous_tone": {},
        **extra_state,
    }

    result = await advance_turn(runtime=runtime, db=db_session, turn_run=turn_run, resume_or_initial=initial_state)

    seen_order = []
    steps_by_type: dict = {}
    while result["status"] == "paused":
        step = result["step"]
        seen_order.append(step.node_type)
        steps_by_type[step.node_type] = step
        result = await resolve_step(
            runtime=runtime, db=db_session, step=step, turn_run=turn_run, action="approve", edited_output=None
        )
    assert result["status"] == "completed"
    return seen_order, steps_by_type


class TestTwistNodeConditionalRouting:
    async def test_skipped_on_a_turn_not_matching_frequency(self, db_session, lm_client_by_model):
        # turn_count=0 -> (0+1) % 5 != 0 -> skipped, same as the default test above.
        seen_order, _ = await _run_full_turn(
            db_session, lm_client_by_model,
            extra_state={"turn_count": 0, "campaign_settings": {"narration_twist_frequency": 5}},
        )
        assert "twist" not in seen_order

    async def test_taken_on_a_turn_matching_frequency(self, db_session, lm_client_by_model):
        # turn_count=4 -> (4+1) % 5 == 0 -> taken, landing between plan_synthesis and narrator.
        seen_order, _ = await _run_full_turn(
            db_session, lm_client_by_model,
            extra_state={"turn_count": 4, "campaign_settings": {"narration_twist_frequency": 5}},
        )
        assert seen_order.index("plan_synthesis") < seen_order.index("twist") < seen_order.index("narrator")

    async def test_disabled_even_on_matching_turn_when_setting_off(self, db_session, lm_client_by_model):
        seen_order, _ = await _run_full_turn(
            db_session, lm_client_by_model,
            extra_state={
                "turn_count": 4,
                "campaign_settings": {"narration_twist_frequency": 5, "narration_twist_enabled": False},
            },
        )
        assert "twist" not in seen_order


class TestRollResolutionConditionalRouting:
    async def test_skipped_when_roll_not_required(self, db_session, lm_client_by_model):
        # Default CANNED_RESPONSES has roll_required=False.
        seen_order, _ = await _run_full_turn(db_session, lm_client_by_model, extra_state={})
        assert "roll_resolution" not in seen_order

    async def test_taken_when_roll_required_and_lands_between_mechanics_and_tone(
        self, db_session, lm_client_by_model
    ):
        responses = {
            **CANNED_RESPONSES,
            "MechanicalCheckOut": {"roll_required": True, "skill": "str", "dc": 10, "reason": "risky lift"},
        }
        seen_order, steps_by_type = await _run_full_turn(
            db_session, lm_client_by_model,
            extra_state={"actor_context": {"ability_scores": {"str": 14}}},
            responses=responses,
        )
        assert (
            seen_order.index("mechanical_check")
            < seen_order.index("roll_resolution")
            < seen_order.index("tone_assessment")
        )
        roll_output = steps_by_type["roll_resolution"].raw_output
        assert roll_output["dc"] == 10
        assert roll_output["ability"] == "str"
        assert roll_output["modifier"] == 2  # str 14 -> (14-10)//2
        assert 1 <= roll_output["rolled"] <= 20
