from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.chain.ops import (
    CreateAncestryDefOp,
    CreateClassDefOp,
    CreateItemDefOp,
    CreateSpellDefOp,
    CreateWorldNodeOp,
    SeedContentOut,
    SeedNarrativeOut,
    WorldOp,
    apply_op,
)
from storybard.chain.prompts import campaign_pitch_prompt, seed_content_prompt, seed_narrative_prompt
from storybard.chain.service import apply_world_update_ops
from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.campaign import Campaign
from storybard.domain.campaign_settings import CampaignSettings
from storybard.domain.inventory import InventoryItem
from storybard.domain.item import DEFAULT_5E_ITEMS, ItemDef
from storybard.domain.narrator import NarratorProfile
from storybard.domain.reveal import PlantedReveal
from storybard.domain.ruleset import (
    DEFAULT_5E_ANCESTRIES,
    DEFAULT_5E_ATTRIBUTES,
    DEFAULT_5E_CLASSES,
    AttributeDefinition,
)
from storybard.domain.spell import DEFAULT_5E_SPELLS
from storybard.services.llm.lmstudio_client import LMStudioClient
from storybard.services.llm.schemas import CampaignPitchOut

# Campaign Seeding — deliberately reuses the exact same WorldOp/apply_op mechanism World
# Update uses (see chain/ops.py's SeedOp/SeedContentOut and chain/service.py's
# apply_world_update_ops, both imported here unchanged), per spec.md "Entity creation":
# v1 had a bespoke seeder and a world-update prompt independently describing "what does
# creating an NPC need," and they drifted apart. One mechanism, two calling contexts.
#
# Stateless propose -> commit, not a stored draft: there's no server-side draft between
# steps — `commit_seed` takes the caller's own (possibly edited) copy of what
# `propose_seed` returned — passing an edited SeedProposal to commit *is* the review step.
#
# Seeding-enrichment settings (seed_npc_count, seed_always_faction, ...) are INPUT
# parameters on SeedInput, not a CampaignSettings read: the campaign (and thus its
# settings row) doesn't exist until commit_seed creates it. commit_seed persists these
# exact values into the new campaign's CampaignSettings row (SeedProposal.settings), so
# every later runtime read reflects what was actually chosen at seed time. See
# domain/campaign_settings.py and the "All 20 Features, Configurable" plan.


class SeedInput(BaseModel):
    campaign_name: str = "New Campaign"
    world_name: str = "Oakhaven"
    world_description: str = "A quiet crossroads town on the edge of a dark forest."
    inspiration_tags: list[str] = []
    races_classes_mode: Literal["standard_5e", "generate"] = "standard_5e"
    narrator_style_description: str = "Plain, direct, spoken-style."
    player_actor_name: str = "Arin"
    must_include: list[str] = []

    # Seeding-enrichment toggles — field names match domain/campaign_settings.py exactly
    # so propose_seed can forward them verbatim into SeedProposal.settings.
    seed_npc_count: int = 3
    seed_hook_count: int = 3
    seed_npc_relationships: bool = True
    seed_rumor_count: int = 3
    seed_location_depth: int = 2
    seed_calendar_from_pitch: bool = True
    seed_always_faction: bool = True
    seed_session_zero: bool = True
    seed_starting_inventory: bool = True
    seed_starting_inventory_count: int = 3
    seed_planted_reveal: bool = True

    # Session-zero content and starting-calendar flavor — free text, only actually stored
    # on the Campaign if their matching toggle above is on (see commit_seed).
    safety_tools: str = ""
    personal_stakes: str = ""
    calendar_context: str = ""


class SeedProposal(BaseModel):
    campaign_name: str
    world_name: str
    world_description: str
    narrator_style_description: str
    player_actor_name: str
    ops: list[dict]
    planted_reveal: str | None = None
    safety_tools: str | None = None
    personal_stakes: str | None = None
    calendar_context: str | None = None
    # Forwarded verbatim into the new campaign's CampaignSettings row — see module
    # docstring above.
    settings: dict = {}


class SeedCommitOut(BaseModel):
    campaign_id: str
    player_actor_id: str
    world_node_id: str
    applied_results: list[dict]


async def generate_seed_input_from_pitch(*, llm: LMStudioClient, model: str, pitch: str) -> SeedInput:
    """The Campaign Pitch quick-start: turns free text into the exact same SeedInput shape
    the Setup form already edits — not a separate concept, just an alternate, faster way to
    fill in the same fields."""
    system, user = campaign_pitch_prompt(pitch=pitch)
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=CampaignPitchOut)
    return SeedInput(**out.model_dump())


_REQUIRED_MECHANICAL_OP_TYPES = {
    "create_ancestry_def", "create_class_def", "create_item_def", "create_spell_def",
}


async def _generate_mechanical_content(
    *, llm: LMStudioClient, model: str, world_description: str, inspiration_tags: list[str], must_include: list[str]
) -> list[dict]:
    """"generate" mode's mechanical content (ancestries/classes/items/spells) — retried
    once if the model badly under-produces (e.g. proposes ancestries but zero classes,
    a real failure observed live: Party Creation is unusable with no class to pick from,
    and the 404 the player hits when a stray empty class_key gets submitted anyway is a
    confusing way to discover it). Never loops more than once — if the retry is still
    incomplete, the caller commits whatever came back; a visibly-incomplete campaign a
    human can immediately notice and re-seed is better than retrying indefinitely against
    a model that may just keep failing the same way."""
    system, user = seed_content_prompt(
        world_description=world_description, inspiration_tags=inspiration_tags, must_include=must_include
    )
    out = await llm.structured_chat(model=model, system=system, user=user, output_model=SeedContentOut)
    op_types = {op.op for op in out.ops}
    if not _REQUIRED_MECHANICAL_OP_TYPES.issubset(op_types):
        out = await llm.structured_chat(model=model, system=system, user=user, output_model=SeedContentOut)
    return [op.model_dump() for op in out.ops]


async def propose_seed(
    *, llm: LMStudioClient, model: str, seed_input: SeedInput, creative_model: str | None = None
) -> SeedProposal:
    ops: list[dict] = []

    if seed_input.races_classes_mode == "standard_5e":
        for a in DEFAULT_5E_ANCESTRIES:
            ops.append(CreateAncestryDefOp(op="create_ancestry_def", **a).model_dump())
        for c in DEFAULT_5E_CLASSES:
            ops.append(CreateClassDefOp(op="create_class_def", **c).model_dump())
        for i in DEFAULT_5E_ITEMS:
            ops.append(CreateItemDefOp(op="create_item_def", **i).model_dump())
        for s in DEFAULT_5E_SPELLS:
            ops.append(CreateSpellDefOp(op="create_spell_def", **s).model_dump())
    else:
        ops.extend(
            await _generate_mechanical_content(
                llm=llm,
                model=model,
                world_description=seed_input.world_description,
                inspiration_tags=seed_input.inspiration_tags,
                must_include=seed_input.must_include,
            )
        )

    ops.append(
        CreateWorldNodeOp(
            op="create_world_node",
            name=seed_input.world_name,
            description=seed_input.world_description,
            parent_node_id=None,
            scale=None,
            x=None,
            y=None,
        ).model_dump()
    )

    # must_include wishes are no longer constructed directly here (title=wish, summary=
    # wish, no beats) — that produced flat, un-elaborated threads (confirmed by a user
    # report: title identical to summary, zero staged beats). They're now handled by the
    # narrative LLM call below, which elaborates each wish into a real thread with a
    # distinct title/summary and staged initial_beats — see seed_narrative_prompt.

    # Narrative content (NPCs, hooks, rumors, an optional faction/locations/planted
    # reveal) — always generated, regardless of races_classes_mode (feature #1: narrative
    # content isn't mechanical content). Routed through creative_model, same reasoning as
    # chain/graph.py's CREATIVE_NODE_TYPES: this is judgment-heavy content generation.
    narrative_system, narrative_user = seed_narrative_prompt(
        world_name=seed_input.world_name,
        world_description=seed_input.world_description,
        inspiration_tags=seed_input.inspiration_tags,
        must_include=seed_input.must_include,
        player_actor_name=seed_input.player_actor_name,
        npc_count=seed_input.seed_npc_count,
        hook_count=seed_input.seed_hook_count,
        rumor_count=seed_input.seed_rumor_count,
        npc_relationships=seed_input.seed_npc_relationships,
        location_depth=seed_input.seed_location_depth,
        include_faction=seed_input.seed_always_faction,
        include_planted_reveal=seed_input.seed_planted_reveal,
    )
    narrative_out = await llm.structured_chat(
        model=creative_model or model, system=narrative_system, user=narrative_user, output_model=SeedNarrativeOut
    )
    ops.extend(op.model_dump() for op in narrative_out.ops)

    settings_fields = {k: v for k, v in seed_input.model_dump().items() if k.startswith("seed_")}

    return SeedProposal(
        campaign_name=seed_input.campaign_name,
        world_name=seed_input.world_name,
        world_description=seed_input.world_description,
        narrator_style_description=seed_input.narrator_style_description,
        player_actor_name=seed_input.player_actor_name,
        ops=ops,
        planted_reveal=narrative_out.planted_reveal if seed_input.seed_planted_reveal else None,
        safety_tools=seed_input.safety_tools if seed_input.seed_session_zero and seed_input.safety_tools else None,
        personal_stakes=(
            seed_input.personal_stakes if seed_input.seed_session_zero and seed_input.personal_stakes else None
        ),
        calendar_context=(
            seed_input.calendar_context if seed_input.seed_calendar_from_pitch and seed_input.calendar_context else None
        ),
        settings=settings_fields,
    )


async def _apply_seeded_locations(
    db: AsyncSession, *, campaign_id: uuid.UUID, location_ops: list[dict]
) -> tuple[list[dict], dict[str, str]]:
    """Applies create_world_node ops in order, resolving a parent_node_id that's a plain
    location NAME (not a real id) against locations already applied earlier in this same
    batch — no location has a real id until commit_seed creates it, so seed_narrative_
    prompt's child locations reference their parent by name instead. A name that doesn't
    resolve against an already-applied location in this batch is rejected with a clear
    reason, never silently dropped (the same "never a silent no-op" principle every other
    cap/gate in chain/ops.py follows). This resolution is scoped to seeding only —
    apply_op's general contract elsewhere (parent_node_id must be a real id) is unchanged.

    Returns (applied_results, name_to_id) — the caller also uses name_to_id to resolve
    create_actor's current_node_id placeholder (see commit_seed) and to find the root
    location's real id (it's keyed by the root's own name, i.e. proposal.world_name).
    """
    applied_results: list[dict] = []
    name_to_id: dict[str, str] = {}
    for raw_op in location_ops:
        parent_ref = raw_op.get("parent_node_id")
        if parent_ref:
            try:
                uuid.UUID(parent_ref)
            except ValueError:
                resolved = name_to_id.get(parent_ref)
                if resolved is None:
                    applied_results.append(
                        {
                            "op": "create_world_node",
                            "applied": False,
                            "reason": f"parent location {parent_ref!r} not found among earlier seeded locations",
                            "entity_id": None,
                        }
                    )
                    continue
                raw_op = {**raw_op, "parent_node_id": resolved}
        op = TypeAdapter(WorldOp).validate_python(raw_op)
        result = await apply_op(db, campaign_id=campaign_id, op=op)
        applied_results.append(
            {
                "op": "create_world_node",
                "applied": result.applied,
                "reason": result.reason,
                "entity_id": str(result.entity_id) if result.entity_id else None,
            }
        )
        if result.applied and result.entity_id:
            name_to_id[raw_op["name"]] = str(result.entity_id)
    return applied_results, name_to_id


async def commit_seed(db: AsyncSession, *, proposal: SeedProposal) -> SeedCommitOut:
    campaign = Campaign(name=proposal.campaign_name)
    if proposal.calendar_context:
        campaign.calendar_context = proposal.calendar_context
    if proposal.safety_tools:
        campaign.safety_tools = proposal.safety_tools
    if proposal.personal_stakes:
        campaign.personal_stakes = proposal.personal_stakes
    db.add(campaign)
    await db.flush()

    db.add(CampaignSettings(campaign_id=campaign.id, **proposal.settings))

    for attr in DEFAULT_5E_ATTRIBUTES:
        db.add(AttributeDefinition(campaign_id=campaign.id, **attr))

    narrator = NarratorProfile(campaign_id=campaign.id, style_description=proposal.narrator_style_description)
    db.add(narrator)
    await db.flush()
    campaign.active_narrator_profile_id = narrator.id

    location_ops = [op for op in proposal.ops if op.get("op") == "create_world_node"]
    other_ops = [op for op in proposal.ops if op.get("op") != "create_world_node"]

    location_results, location_name_to_id = await _apply_seeded_locations(
        db, campaign_id=campaign.id, location_ops=location_ops
    )

    # create_actor's current_node_id carries the same name-placeholder scheme as
    # create_world_node's parent_node_id (see seed_narrative_prompt) — resolved here
    # against the same name_to_id map before the normal batch apply.
    #
    # Collision backstop: seed_narrative_prompt is told not to reuse the player's name for
    # an NPC, but nothing enforces that structurally on the LLM side — confirmed live, a
    # generated NPC named identically to the player produced a Narrator that described the
    # same name as both "you" and a separate third-person figure in the same scene. Reject
    # (don't silently rename) a colliding create_actor here, matching this codebase's
    # existing "never trust the LLM, enforce in code" gating elsewhere in apply_op —
    # skipping one NPC is a safe degradation, inventing a rename is not.
    player_name_lower = proposal.player_actor_name.strip().lower()
    resolved_other_ops = []
    collision_results: list[dict] = []
    for raw_op in other_ops:
        if raw_op.get("op") == "create_actor" and raw_op.get("name", "").strip().lower() == player_name_lower:
            collision_results.append(
                {
                    "op": "create_actor",
                    "applied": False,
                    "reason": f"name {raw_op.get('name')!r} collides with the player character's name",
                    "entity_id": None,
                }
            )
            continue
        current_node_ref = raw_op.get("current_node_id")
        if current_node_ref and current_node_ref in location_name_to_id:
            raw_op = {**raw_op, "current_node_id": location_name_to_id[current_node_ref]}
        resolved_other_ops.append(raw_op)

    other_applied = await apply_world_update_ops(db, campaign_id=campaign.id, resolved={"ops": resolved_other_ops})
    applied_results = location_results + other_applied["applied_results"] + collision_results

    world_node_id_raw = location_name_to_id.get(proposal.world_name)
    world_node_id = uuid.UUID(world_node_id_raw) if world_node_id_raw else None

    player = Actor(
        campaign_id=campaign.id, name=proposal.player_actor_name, kind="player", current_node_id=world_node_id
    )
    db.add(player)
    await db.flush()

    db.add(ActorProfile(actor_id=player.id))
    db.add(CharacterSheet(actor_id=player.id, ability_scores={a["key"]: 10 for a in DEFAULT_5E_ATTRIBUTES}))
    await db.flush()

    if proposal.planted_reveal and proposal.settings.get("seed_planted_reveal", True):
        db.add(PlantedReveal(campaign_id=campaign.id, secret_text=proposal.planted_reveal, connects_entity_ids=[]))

    if proposal.settings.get("seed_starting_inventory", True):
        items = (await db.execute(select(ItemDef).where(ItemDef.campaign_id == campaign.id))).scalars().all()
        count = proposal.settings.get("seed_starting_inventory_count", 3)
        for item in items[:count]:
            db.add(InventoryItem(campaign_id=campaign.id, owner_actor_id=player.id, item_def_id=item.id, quantity=1))
        await db.flush()

    return SeedCommitOut(
        campaign_id=str(campaign.id),
        player_actor_id=str(player.id),
        world_node_id=world_node_id_raw or "",
        applied_results=applied_results,
    )
