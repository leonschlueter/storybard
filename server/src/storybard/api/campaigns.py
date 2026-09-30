from __future__ import annotations

import uuid

import structlog
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
from storybard.domain.campaign_settings import CampaignSettings
from storybard.domain.narrator import NarratorProfile
from storybard.domain.ruleset import DEFAULT_5E_ATTRIBUTES, AttributeDefinition
from storybard.domain.world import WorldNode
from storybard.services.context_assembly import get_campaign_settings

log = structlog.get_logger()

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
    log.info("seed.pitch_started")
    result = await generate_seed_input_from_pitch(llm=runtime.llm, model=runtime.model, pitch=body.pitch)
    log.info("seed.pitch_completed")
    return result


@router.post("/seed/propose", response_model=SeedProposal)
async def propose_seed_route(
    body: SeedInput, runtime: ChainRuntime = Depends(get_chain_runtime)
) -> SeedProposal:
    # Request-level logging independent of LMStudioClient's own — this whole route used
    # to be a total black box in `docker logs`: no line at all until (if ever) it
    # returned, indistinguishable from a genuine hang. See the live debugging session
    # that motivated this.
    log.info("seed.propose_started", mode=body.races_classes_mode)
    result = await propose_seed(
        llm=runtime.llm, model=runtime.model, creative_model=runtime.creative_model, seed_input=body
    )
    log.info("seed.propose_completed", op_count=len(result.ops))
    return result


@router.post("/seed/commit", response_model=SeedCommitOut)
async def commit_seed_route(body: SeedProposal, db: AsyncSession = Depends(get_db)) -> SeedCommitOut:
    log.info("seed.commit_started", op_count=len(body.ops))
    result = await commit_seed(db, proposal=body)
    await db.commit()
    log.info("seed.commit_completed", campaign_id=result.campaign_id)
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


# CampaignSettings — the real "configurable" surface for the 20 seeding/narration
# features (see services/context_assembly.py::get_campaign_settings and the "All 20
# Features" plan). One field per feature; PATCH only updates the fields it's given
# (exclude_unset), so a partial body never resets the rest to their defaults.


class CampaignSettingsOut(BaseModel):
    seed_npc_count: int
    seed_hook_count: int
    seed_npc_relationships: bool
    seed_rumor_count: int
    seed_location_depth: int
    seed_calendar_from_pitch: bool
    seed_always_faction: bool
    seed_session_zero: bool
    seed_starting_inventory: bool
    seed_starting_inventory_count: int
    seed_planted_reveal: bool
    narration_npc_offscreen: bool
    narration_npc_offscreen_interval_hours: int
    narration_twist_enabled: bool
    narration_twist_frequency: int
    narration_npc_voices: bool
    narration_consequence_ledger: bool
    narration_hard_stagnation_threshold: int
    mechanical_degrees_of_success: bool
    narration_thinking_gloss: bool
    narration_oracle_enabled: bool
    narration_npc_memory: bool

    model_config = {"from_attributes": True}


class CampaignSettingsPatchIn(BaseModel):
    seed_npc_count: int | None = None
    seed_hook_count: int | None = None
    seed_npc_relationships: bool | None = None
    seed_rumor_count: int | None = None
    seed_location_depth: int | None = None
    seed_calendar_from_pitch: bool | None = None
    seed_always_faction: bool | None = None
    seed_session_zero: bool | None = None
    seed_starting_inventory: bool | None = None
    seed_starting_inventory_count: int | None = None
    seed_planted_reveal: bool | None = None
    narration_npc_offscreen: bool | None = None
    narration_npc_offscreen_interval_hours: int | None = None
    narration_twist_enabled: bool | None = None
    narration_twist_frequency: int | None = None
    narration_npc_voices: bool | None = None
    narration_consequence_ledger: bool | None = None
    narration_hard_stagnation_threshold: int | None = None
    mechanical_degrees_of_success: bool | None = None
    narration_thinking_gloss: bool | None = None
    narration_oracle_enabled: bool | None = None
    narration_npc_memory: bool | None = None


@router.get("/{campaign_id}/settings", response_model=CampaignSettingsOut)
async def get_settings(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> CampaignSettings:
    settings = await get_campaign_settings(db, campaign_id=campaign_id)
    await db.commit()
    return settings


@router.patch("/{campaign_id}/settings", response_model=CampaignSettingsOut)
async def patch_settings(
    campaign_id: uuid.UUID, body: CampaignSettingsPatchIn, db: AsyncSession = Depends(get_db)
) -> CampaignSettings:
    settings = await get_campaign_settings(db, campaign_id=campaign_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return settings
