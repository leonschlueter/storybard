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
    "WorldUpdateOut": {"ops": []},
    "NarratorOut": {"narration": "You walk into town."},
    "CreateMemoryOut": {
        "memories": [{"title": "Arrived in town", "text": "I arrived in town.", "importance": 2}],
        "campaign_summary_update": "The party has just arrived in town.",
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
    runtime = build_graph(llm=llm, model="test-model")

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
