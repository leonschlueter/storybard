from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from storybard.chain.ops import CreateMemoryOut, WorldUpdateOut
from storybard.chain.prompts import (
    intent_prompt,
    mechanical_check_prompt,
    memory_regression_prompt,
    narrator_prompt,
    opportunity_spotting_prompt,
    plan_synthesis_prompt,
    plausibility_prompt,
    thread_tick_prompt,
    tone_assessment_prompt,
    world_update_prompt,
)
from storybard.services.llm.lmstudio_client import LMStudioClient
from storybard.services.llm.schemas import (
    IntentOut,
    MechanicalCheckOut,
    NarratorOut,
    OpportunitySpottingOut,
    PlanSynthesisOut,
    PlausibilityOut,
    ThreadTickOut,
    ToneAssessmentOut,
)

# Opportunity Spotting / Plan Synthesis / World Update — the judgment-heavy "should
# something structural happen here" nodes — get a higher temperature than the
# StrictOut-schema default (0.2). Confirmed live: at 0.2, both the default small model and
# a much larger one consistently defaulted to proposing nothing even when the narration and
# an available hook idea both clearly warranted a Thread/Clock — replaying the exact same
# prompt at 0.7 against the larger model reliably produced the right structural op. The
# rest of the chain (intent parsing, plausibility, mechanical checks, tone) stays at the
# low-temperature default, where reliability matters more than willingness to act.
_CREATIVE_TEMPERATURE = 0.7


class ChainState(TypedDict, total=False):
    player_text: str
    mode: str
    scene_text: str
    style_description: str
    verbosity_words: float
    active_threads: list[dict]
    active_clocks: list[dict]
    known_actors: list[dict]
    known_locations: list[dict]
    previous_tone: dict
    actor_context: dict
    recent_turns: list[dict]
    relevant_memories: list[dict]
    recent_world_events: list[dict]
    campaign_summary: str
    turn_count: int
    turns_since_thread_activity: int

    intent: dict
    plausibility: dict
    thread_tick: dict
    opportunity_spotting: dict
    mechanical_check: dict
    tone: dict
    plan: str
    world_update: dict
    narration: str
    memory_regression: dict

    # Staging keys: a "_generate" node proposes here, the paired "_review" node reads it
    # via interrupt() and writes the (possibly edited) result into the real key above.
    # Must be declared here — LangGraph's state reducer only merges keys present in this
    # schema; an undeclared key in a node's returned dict is silently dropped, not an error.
    _proposed_intent: dict
    _proposed_plausibility: dict
    _proposed_thread_tick: dict
    _proposed_opportunity_spotting: dict
    _proposed_mechanical_check: dict
    _proposed_tone: dict
    _proposed_plan: dict
    _proposed_world_update: dict
    _proposed_narration: dict
    _proposed_memory_regression: dict


# Each conceptual step is TWO graph nodes: "_generate" (calls the LLM, fully completes and
# checkpoints) and "_review" (calls interrupt() as its first action). This split matters:
# LangGraph re-runs a node's code from the top on resume, so if the LLM call sat *before*
# the interrupt() in the same node, resuming would silently re-call the LLM (wasted call,
# and a different result than what was actually reviewed). Splitting means resuming only
# re-enters "_review", which does nothing but resolve the interrupt.


def _review_node(node_type: str, state_key: str):
    async def node(state: ChainState) -> dict:
        proposed = state[f"_proposed_{state_key}"]  # type: ignore[literal-required]
        resolved = interrupt({"node_type": node_type, "proposed": proposed})
        return {state_key: resolved}

    return node


async def intent_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = intent_prompt(
        player_text=state["player_text"],
        mode=state.get("mode", "explore"),
        recent_turns=state.get("recent_turns", []),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=IntentOut)
    return {"_proposed_intent": out.model_dump()}


async def plausibility_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = plausibility_prompt(
        player_text=state["player_text"],
        intent=state["intent"],
        scene_text=state.get("scene_text", ""),
        actor_context=state.get("actor_context", {}),
        campaign_summary=state.get("campaign_summary", ""),
        recent_turns=state.get("recent_turns", []),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=PlausibilityOut)
    return {"_proposed_plausibility": out.model_dump()}


async def thread_tick_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = thread_tick_prompt(
        player_text=state["player_text"],
        active_clocks=state.get("active_clocks", []),
        recent_turns=state.get("recent_turns", []),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=ThreadTickOut)
    return {"_proposed_thread_tick": out.model_dump()}


async def opportunity_spotting_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = opportunity_spotting_prompt(
        player_text=state["player_text"],
        plausibility=state["plausibility"],
        active_threads=state.get("active_threads", []),
        scene_text=state.get("scene_text", ""),
        actor_context=state.get("actor_context", {}),
        recent_turns=state.get("recent_turns", []),
    )
    out = await llm.structured_chat(
        model=model, system=system, user=user, output_model=OpportunitySpottingOut, temperature=_CREATIVE_TEMPERATURE
    )
    return {"_proposed_opportunity_spotting": out.model_dump()}


async def mechanical_check_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = mechanical_check_prompt(
        player_text=state["player_text"],
        plausibility=state["plausibility"],
        turn_count=state.get("turn_count", 0),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=MechanicalCheckOut)
    return {"_proposed_mechanical_check": out.model_dump()}


async def tone_assessment_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = tone_assessment_prompt(
        player_text=state["player_text"],
        plausibility=state["plausibility"],
        mechanical_check=state["mechanical_check"],
        previous_tone=state.get("previous_tone", {}),
        recent_turns=state.get("recent_turns", []),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=ToneAssessmentOut)
    return {"_proposed_tone": out.model_dump()}


async def plan_synthesis_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = plan_synthesis_prompt(
        player_text=state["player_text"],
        plausibility=state["plausibility"],
        mechanical_check=state["mechanical_check"],
        thread_tick=state.get("thread_tick", {}),
        opportunity_spotting=state.get("opportunity_spotting", {}),
        tone=state.get("tone", {}),
        campaign_summary=state.get("campaign_summary", ""),
        recent_turns=state.get("recent_turns", []),
        turns_since_thread_activity=state.get("turns_since_thread_activity", 0),
        turn_count=state.get("turn_count", 0),
    )
    out = await llm.structured_chat(
        model=model, system=system, user=user, output_model=PlanSynthesisOut, temperature=_CREATIVE_TEMPERATURE
    )
    return {"_proposed_plan": out.model_dump()}


async def world_update_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = world_update_prompt(
        player_text=state["player_text"],
        plausibility=state["plausibility"],
        mechanical_check=state["mechanical_check"],
        active_threads=state.get("active_threads", []),
        thread_tick_suggestions=state.get("thread_tick", {}).get("tick_suggestions", []),
        hook_ideas=state.get("opportunity_spotting", {}).get("hook_ideas", []),
        known_actors=state.get("known_actors", []),
        known_locations=state.get("known_locations", []),
        narration=state.get("narration", ""),
        recent_turns=state.get("recent_turns", []),
    )
    out = await llm.structured_chat(
        model=model, system=system, user=user, output_model=WorldUpdateOut, temperature=_CREATIVE_TEMPERATURE
    )
    return {"_proposed_world_update": out.model_dump()}


async def narrator_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    plan_state = state.get("plan", {})
    plan_text = plan_state.get("plan", "") if isinstance(plan_state, dict) else ""
    system, user = narrator_prompt(
        player_text=state["player_text"],
        plausibility=state["plausibility"],
        mechanical_check=state["mechanical_check"],
        plan=plan_text,
        tone=state.get("tone", {}),
        style_description=state.get("style_description", ""),
        verbosity_words=state.get("verbosity_words", 150.0),
        scene_text=state.get("scene_text", ""),
        actor_context=state.get("actor_context", {}),
        recent_turns=state.get("recent_turns", []),
        relevant_memories=state.get("relevant_memories", []),
        known_actors=state.get("known_actors", []),
        known_locations=state.get("known_locations", []),
        recent_world_events=state.get("recent_world_events", []),
        campaign_summary=state.get("campaign_summary", ""),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=NarratorOut)
    return {"_proposed_narration": out.model_dump()}


def _narration_review_node():
    async def node(state: ChainState) -> dict:
        proposed = state["_proposed_narration"]  # type: ignore[typeddict-item]
        resolved = interrupt({"node_type": "narrator", "proposed": proposed})
        return {"narration": resolved["narration"]}

    return node


async def memory_regression_generate(state: ChainState, *, llm: LMStudioClient, model: str) -> dict:
    system, user = memory_regression_prompt(
        player_text=state["player_text"],
        narration=state.get("narration", ""),
        previous_summary=state.get("campaign_summary", ""),
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=CreateMemoryOut)
    return {"_proposed_memory_regression": out.model_dump()}


@dataclass
class ChainRuntime:
    """The compiled graph plus the LLM client/model it was built against — kept together
    since the `retry` path needs to call the LLM directly, outside the graph."""

    graph: Any
    llm: LMStudioClient
    model: str


def _bind(generate_fn, *, llm: LMStudioClient, model: str):
    """Binds llm/model onto an async node function via a real `async def` closure — a
    lambda wrapping an async call returns a coroutine but isn't itself a coroutine
    function, and LangGraph checks iscoroutinefunction() to decide whether to await it."""

    async def node(state: ChainState) -> dict:
        return await generate_fn(state, llm=llm, model=model)

    return node


def build_graph(*, llm: LMStudioClient, model: str) -> ChainRuntime:
    graph = StateGraph(ChainState)

    graph.add_node("intent_generate", _bind(intent_generate, llm=llm, model=model))
    graph.add_node("intent_review", _review_node("intent_parse", "intent"))
    graph.add_node("plausibility_generate", _bind(plausibility_generate, llm=llm, model=model))
    graph.add_node("plausibility_review", _review_node("plausibility_check", "plausibility"))
    graph.add_node("thread_tick_generate", _bind(thread_tick_generate, llm=llm, model=model))
    graph.add_node("thread_tick_review", _review_node("thread_tick", "thread_tick"))
    graph.add_node("opportunity_spotting_generate", _bind(opportunity_spotting_generate, llm=llm, model=model))
    graph.add_node("opportunity_spotting_review", _review_node("opportunity_spotting", "opportunity_spotting"))
    graph.add_node("mechanical_check_generate", _bind(mechanical_check_generate, llm=llm, model=model))
    graph.add_node("mechanical_check_review", _review_node("mechanical_check", "mechanical_check"))
    graph.add_node("tone_assessment_generate", _bind(tone_assessment_generate, llm=llm, model=model))
    graph.add_node("tone_assessment_review", _review_node("tone_assessment", "tone"))
    graph.add_node("plan_synthesis_generate", _bind(plan_synthesis_generate, llm=llm, model=model))
    graph.add_node("plan_synthesis_review", _review_node("plan_synthesis", "plan"))
    graph.add_node("world_update_generate", _bind(world_update_generate, llm=llm, model=model))
    graph.add_node("world_update_review", _review_node("world_update", "world_update"))
    graph.add_node("narrator_generate", _bind(narrator_generate, llm=llm, model=model))
    graph.add_node("narrator_review", _narration_review_node())
    graph.add_node("memory_regression_generate", _bind(memory_regression_generate, llm=llm, model=model))
    graph.add_node("memory_regression_review", _review_node("memory_regression", "memory_regression"))

    graph.set_entry_point("intent_generate")
    graph.add_edge("intent_generate", "intent_review")
    graph.add_edge("intent_review", "plausibility_generate")
    graph.add_edge("plausibility_generate", "plausibility_review")
    graph.add_edge("plausibility_review", "thread_tick_generate")
    graph.add_edge("thread_tick_generate", "thread_tick_review")
    graph.add_edge("thread_tick_review", "opportunity_spotting_generate")
    graph.add_edge("opportunity_spotting_generate", "opportunity_spotting_review")
    graph.add_edge("opportunity_spotting_review", "mechanical_check_generate")
    graph.add_edge("mechanical_check_generate", "mechanical_check_review")
    graph.add_edge("mechanical_check_review", "tone_assessment_generate")
    graph.add_edge("tone_assessment_generate", "tone_assessment_review")
    graph.add_edge("tone_assessment_review", "plan_synthesis_generate")
    graph.add_edge("plan_synthesis_generate", "plan_synthesis_review")
    graph.add_edge("plan_synthesis_review", "narrator_generate")
    graph.add_edge("narrator_generate", "narrator_review")
    # World Update runs AFTER the Narrator (not before) — it needs the actual narration to
    # know what entities/threads/clocks the beat just introduced. World Update running
    # first meant it could only ever guess blind at structural changes before the prose
    # that would justify them existed; any NPC/location the Narrator improvised mid-scene
    # was structurally invisible forever. See the "Entity Grounding" plan.
    graph.add_edge("narrator_review", "world_update_generate")
    graph.add_edge("world_update_generate", "world_update_review")
    graph.add_edge("world_update_review", "memory_regression_generate")
    graph.add_edge("memory_regression_generate", "memory_regression_review")
    graph.add_edge("memory_regression_review", END)

    checkpointer = InMemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)
    return ChainRuntime(graph=compiled, llm=llm, model=model)
