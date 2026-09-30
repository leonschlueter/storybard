from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# `extra="forbid"` matters far more than it looks: it's what makes Pydantic emit
# `"additionalProperties": false` in the JSON schema handed to LM Studio. Without it (and
# without every field being required), grammar-constrained decoding has nothing to actually
# constrain — confirmed empirically: with a permissive schema, gemma-4-e4b returned
# `{"action": "move", "target_type": "place"}` for IntentOut (wrong keys entirely) and it
# validated anyway, silently defaulting `primitive` to "unknown", because nothing in the
# schema *required* the right keys or forbade the wrong ones. With `extra="forbid"` +
# every field required, the same prompt correctly produced `primitive: "move"`. Every
# schema below is required-fields-only for this reason — a field being merely *nullable*
# (`X | None`) is fine and still forces the model to explicitly commit to that key; a field
# having a Python-level *default* is what reopens the loophole.


class StrictOut(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentOut(StrictOut):
    primitive: Literal[
        "move", "speak", "interact", "inspect", "use_item", "cast_spell",
        "rest", "wait", "attack", "unknown",
    ]
    target: str | None
    notes: list[str]


class PlausibilityOut(StrictOut):
    feasibility: Literal["feasible", "feasible_with_twist", "not_feasible"]
    reason: str
    twist: str | None
    # Free text ("10 minutes", "3 weeks") — descriptive content, not a structural field, so
    # per the tone-assessment precedent this stays free text; parsed by
    # services/duration.py rather than constrained tighter at the LLM layer.
    time_passed: str | None


class MechanicalCheckOut(StrictOut):
    roll_required: bool
    # The governing ability, not a free-text skill name — this engine has never tracked
    # skill-proficiency bonuses (CharacterSheet.proficiencies isn't consulted anywhere in
    # mechanics), so resolving directly against the raw ability is an honest simplification
    # matching the existing mechanical depth, not a new one. Lets services/mechanics/dice.py
    # resolve a real roll without needing a skill->ability mapping table.
    skill: Literal["str", "dex", "con", "int", "wis", "cha"] | None
    dc: int | None
    reason: str


class TickSuggestion(StrictOut):
    clock_id: str
    delta: int
    reason: str


class ThreadTickOut(StrictOut):
    """Advisory only — see chain/graph.py. These suggestions are folded into World
    Update's prompt as context; World Update's own `tick_clock` op is what actually
    commits a tick."""

    tick_suggestions: list[TickSuggestion]


class HookIdea(StrictOut):
    proposed_text: str
    touches_entity_id: str | None


class OpportunitySpottingOut(StrictOut):
    """Advisory only, same reasoning as ThreadTickOut — World Update turns ones it agrees
    with into real `propose_hook` ops."""

    hook_ideas: list[HookIdea]


class ToneAssessmentOut(StrictOut):
    # Free text, not a fixed enum — tone is inherently descriptive ("grim but darkly
    # comic," "quietly unsettling"), and a closed list of buckets loses real expressiveness
    # for something this subjective. Unlike the structural fields the strict-schema lesson
    # is about (op names, discriminators), this is content, same category as `reason` or
    # `narration` elsewhere — free text there was never the problem.
    tension: str
    drivers: list[str]


class PlanSynthesisOut(StrictOut):
    plan: str


class RollResolutionOut(BaseModel):
    """NOT a StrictOut — this is never sent through grammar-constrained decoding, since
    nothing calls an LLM to produce it (services/mechanics/dice.py::resolve_check computes
    it deterministically). Kept here only so chain/service.py::NODE_OUTPUT_MODELS has one
    place to look, matching every other node's output model, and so a human reviewing a
    ChainStep can still "edit" it (override the rolled numbers) through the same generic
    edit-validation path every other node uses."""

    rolled: int
    modifier: int
    total: int
    dc: int
    ability: str
    degree: Literal[
        "critical_success", "clean_success", "narrow_success",
        "narrow_failure", "clean_failure", "critical_failure",
    ]


class NpcOffscreenOut(StrictOut):
    """One NPC's off-screen action while the player isn't watching (feature #11, "All 20
    Features" plan) — /world-tick's NPC simulation call, see chain/prompts.py's
    npc_offscreen_prompt."""

    event: str


class TwistOut(StrictOut):
    """The Twist node's single output — a low-frequency complication injected separately
    from Plan Synthesis's every-turn beat planning (feature #12, "All 20 Features" plan).
    Only reached on a conditional edge (chain/graph.py's _route_after_plan_synthesis),
    not every turn, so it can afford to be bolder than Plan Synthesis's routine pacing."""

    complication: str


class NarratorOut(StrictOut):
    narration: str


class CampaignPitchOut(StrictOut):
    """The Campaign Pitch quick-start's output target — mirrors chain/seed_service.py's
    original SeedInput fields plus calendar_context, StrictOut-compliant (no Python-level
    defaults, since this is an LLM output target, not an API input with convenience
    defaults). SeedInput's newer seeding-toggle fields (seed_npc_count, etc.) aren't asked
    of the LLM here — those are wizard settings, not something a one-paragraph pitch
    implies; generate_seed_input_from_pitch's SeedInput(**out.model_dump()) leaves them at
    their normal defaults."""

    campaign_name: str
    world_name: str
    world_description: str
    inspiration_tags: list[str]
    races_classes_mode: Literal["standard_5e", "generate"]
    narrator_style_description: str
    player_actor_name: str
    must_include: list[str]
    # Short descriptive starting-calendar flavor implied by the pitch (e.g. "early winter,
    # three days before the harvest festival") — free text, not a real datetime parse; see
    # SeedInput.calendar_context and Campaign.calendar_context.
    calendar_context: str
