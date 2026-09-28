from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.chain.ops import (
    CreateAncestryDefOp,
    CreateClassDefOp,
    CreateItemDefOp,
    CreateMajorThreadOp,
    CreateSpellDefOp,
    CreateWorldNodeOp,
    SeedContentOut,
)
from storybard.chain.prompts import campaign_pitch_prompt, seed_content_prompt
from storybard.chain.service import apply_world_update_ops
from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.campaign import Campaign
from storybard.domain.narrator import NarratorProfile
from storybard.domain.ruleset import (
    DEFAULT_5E_ANCESTRIES,
    DEFAULT_5E_ATTRIBUTES,
    DEFAULT_5E_CLASSES,
    AttributeDefinition,
)
from storybard.domain.item import DEFAULT_5E_ITEMS
from storybard.domain.spell import DEFAULT_5E_SPELLS
from storybard.services.llm.lmstudio_client import LMStudioClient
from storybard.services.llm.schemas import CampaignPitchOut

# Campaign Seeding — deliberately reuses the exact same WorldOp/apply_op mechanism World
# Update uses (see chain/ops.py's SeedOp/SeedContentOut and chain/service.py's
# apply_world_update_ops, both imported here unchanged), per spec.md "Entity creation":
# v1 had a bespoke seeder and a world-update prompt independently describing "what does
# creating an NPC need," and they drifted apart. One mechanism, two calling contexts.
#
# Stateless propose -> commit, not a stored draft: there's no Seed Wizard UI yet (that's
# Phase 3C) to hold a server-side draft between steps, so `commit_seed` takes the caller's
# own (possibly edited) copy of what `propose_seed` returned — passing an edited
# SeedProposal to commit *is* the review step, the same way an "edit" action on a ChainStep
# is the review step during regular play.


class SeedInput(BaseModel):
    campaign_name: str = "New Campaign"
    world_name: str = "Oakhaven"
    world_description: str = "A quiet crossroads town on the edge of a dark forest."
    inspiration_tags: list[str] = []
    races_classes_mode: Literal["standard_5e", "generate"] = "standard_5e"
    narrator_style_description: str = "Plain, direct, spoken-style."
    player_actor_name: str = "Arin"
    must_include: list[str] = []


class SeedProposal(BaseModel):
    campaign_name: str
    world_name: str
    world_description: str
    narrator_style_description: str
    player_actor_name: str
    ops: list[dict]


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


async def propose_seed(*, llm: LMStudioClient, model: str, seed_input: SeedInput) -> SeedProposal:
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
        system, user = seed_content_prompt(
            world_description=seed_input.world_description,
            inspiration_tags=seed_input.inspiration_tags,
            must_include=seed_input.must_include,
        )
        out = await llm.structured_chat(model=model, system=system, user=user, output_model=SeedContentOut)
        ops.extend(op.model_dump() for op in out.ops)

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

    for wish in seed_input.must_include:
        ops.append(
            CreateMajorThreadOp(
                op="create_major_thread", title=wish, summary=wish, owner_type="campaign", owner_id=None
            ).model_dump()
        )

    return SeedProposal(
        campaign_name=seed_input.campaign_name,
        world_name=seed_input.world_name,
        world_description=seed_input.world_description,
        narrator_style_description=seed_input.narrator_style_description,
        player_actor_name=seed_input.player_actor_name,
        ops=ops,
    )


async def commit_seed(db: AsyncSession, *, proposal: SeedProposal) -> SeedCommitOut:
    campaign = Campaign(name=proposal.campaign_name)
    db.add(campaign)
    await db.flush()

    for attr in DEFAULT_5E_ATTRIBUTES:
        db.add(AttributeDefinition(campaign_id=campaign.id, **attr))

    narrator = NarratorProfile(campaign_id=campaign.id, style_description=proposal.narrator_style_description)
    db.add(narrator)
    await db.flush()
    campaign.active_narrator_profile_id = narrator.id

    applied = await apply_world_update_ops(db, campaign_id=campaign.id, resolved={"ops": proposal.ops})
    applied_results = applied["applied_results"]

    world_node_id_raw = next(
        (r["entity_id"] for r in applied_results if r["op"] == "create_world_node" and r["applied"]), None
    )
    world_node_id = uuid.UUID(world_node_id_raw) if world_node_id_raw else None

    player = Actor(
        campaign_id=campaign.id, name=proposal.player_actor_name, kind="player", current_node_id=world_node_id
    )
    db.add(player)
    await db.flush()

    db.add(ActorProfile(actor_id=player.id))
    db.add(CharacterSheet(actor_id=player.id, ability_scores={a["key"]: 10 for a in DEFAULT_5E_ATTRIBUTES}))
    await db.flush()

    return SeedCommitOut(
        campaign_id=str(campaign.id),
        player_actor_id=str(player.id),
        world_node_id=world_node_id_raw or "",
        applied_results=applied_results,
    )
