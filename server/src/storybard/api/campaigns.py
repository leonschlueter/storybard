from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.api.turns import get_chain_runtime
from storybard.chain.graph import ChainRuntime
from storybard.chain.seed_service import (
    SeedCommitOut,
    SeedInput,
    SeedProposal,
    commit_seed,
    generate_seed_input_from_pitch,
    propose_seed,
)
from storybard.core.db import get_db
from storybard.domain.actor import Actor, ActorProfile, CharacterSheet
from storybard.domain.campaign import Campaign
from storybard.domain.narrator import NarratorProfile
from storybard.domain.ruleset import DEFAULT_5E_ATTRIBUTES, AttributeDefinition
from storybard.domain.world import WorldNode

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreateIn(BaseModel):
    name: str = "Dev Campaign"
    world_node_name: str = "Oakhaven"
    world_node_description: str = "A quiet crossroads town."
    player_actor_name: str = "Arin"
    narrator_style_description: str = "Plain, direct, spoken-style."


class CampaignCreateOut(BaseModel):
    campaign_id: uuid.UUID
    player_actor_id: uuid.UUID
    world_node_id: uuid.UUID


@router.post("", response_model=CampaignCreateOut)
async def create_campaign(body: CampaignCreateIn, db: AsyncSession = Depends(get_db)) -> CampaignCreateOut:
    campaign = Campaign(name=body.name)
    db.add(campaign)
    await db.flush()

    for attr in DEFAULT_5E_ATTRIBUTES:
        db.add(AttributeDefinition(campaign_id=campaign.id, **attr))

    node = WorldNode(
        campaign_id=campaign.id, name=body.world_node_name, description=body.world_node_description
    )
    db.add(node)
    await db.flush()

    narrator = NarratorProfile(campaign_id=campaign.id, style_description=body.narrator_style_description)
    db.add(narrator)
    await db.flush()
    campaign.active_narrator_profile_id = narrator.id

    player = Actor(
        campaign_id=campaign.id, name=body.player_actor_name, kind="player", current_node_id=node.id
    )
    db.add(player)
    await db.flush()

    db.add(ActorProfile(actor_id=player.id))
    db.add(
        CharacterSheet(
            actor_id=player.id,
            ability_scores={a["key"]: 10 for a in DEFAULT_5E_ATTRIBUTES},
        )
    )

    await db.commit()
    return CampaignCreateOut(campaign_id=campaign.id, player_actor_id=player.id, world_node_id=node.id)


# Campaign Seeding — a guided propose→review→commit flow that reuses the exact same
# WorldOp/apply_op mechanism World Update uses (chain/seed_service.py), per spec.md
# "Entity creation". `POST /campaigns` above is now only a quick/dev-skeleton path — the
# Seed Wizard UI (Phase 3C) calls these instead; `POST /campaigns` is unused by the
# frontend but left in place for quick dev testing.


class CampaignPitchIn(BaseModel):
    pitch: str


@router.post("/seed/pitch", response_model=SeedInput)
async def pitch_seed_route(
    body: CampaignPitchIn, runtime: ChainRuntime = Depends(get_chain_runtime)
) -> SeedInput:
    return await generate_seed_input_from_pitch(llm=runtime.llm, model=runtime.model, pitch=body.pitch)


@router.post("/seed/propose", response_model=SeedProposal)
async def propose_seed_route(
    body: SeedInput, runtime: ChainRuntime = Depends(get_chain_runtime)
) -> SeedProposal:
    return await propose_seed(llm=runtime.llm, model=runtime.model, seed_input=body)


@router.post("/seed/commit", response_model=SeedCommitOut)
async def commit_seed_route(body: SeedProposal, db: AsyncSession = Depends(get_db)) -> SeedCommitOut:
    result = await commit_seed(db, proposal=body)
    await db.commit()
    return result


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "mode": campaign.mode,
        "turn_count": campaign.turn_count,
        "current_datetime": campaign.current_datetime.isoformat(),
    }
