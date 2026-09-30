from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.core.db import get_db
from storybard.domain.actor import CharacterSheet
from storybard.domain.inventory import InventoryItem
from storybard.domain.item import ItemDef
from storybard.domain.ruleset import AncestryDef, AttributeDefinition, ClassDef
from storybard.services.mechanics.formulas import POINT_BUY_POOL, ability_mod, point_buy_cost

router = APIRouter(prefix="/campaigns", tags=["party"])

# Party Creation (spec.md Step 7). Dice rolling happens client-side (no adversarial
# multiplayer concern in a solo local game); point-buy's cost-curve validation happens
# here, server-side, since it's a structural correctness guardrail — matches every other
# cap in this codebase being enforced in code, never trusted to the client.


@router.get("/{campaign_id}/character-options")
async def get_character_options(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    attrs = (
        await db.execute(
            select(AttributeDefinition)
            .where(AttributeDefinition.campaign_id == campaign_id)
            .order_by(AttributeDefinition.sort_order)
        )
    ).scalars().all()
    ancestries = (
        await db.execute(select(AncestryDef).where(AncestryDef.campaign_id == campaign_id))
    ).scalars().all()
    classes = (await db.execute(select(ClassDef).where(ClassDef.campaign_id == campaign_id))).scalars().all()

    return {
        "attribute_definitions": [
            {"key": a.key, "display_name": a.display_name, "abbreviation": a.abbreviation, "sort_order": a.sort_order}
            for a in attrs
        ],
        "ancestry_defs": [
            {"key": a.key, "name": a.name, "description": a.description, "speed": a.speed, "features": a.features}
            for a in ancestries
        ],
        "class_defs": [
            {
                "key": c.key, "name": c.name, "description": c.description, "hit_die": c.hit_die,
                "primary_attribute_key": c.primary_attribute_key, "proficiencies": c.proficiencies,
                "spellcasting": c.spellcasting, "starting_equipment": c.starting_equipment,
            }
            for c in classes
        ],
    }


class FinalizeCharacterIn(BaseModel):
    ancestry_key: str
    class_key: str
    method: Literal["roll", "point_buy"]
    ability_scores: dict[str, int]


class FinalizeCharacterOut(BaseModel):
    actor_id: uuid.UUID
    ancestry: str
    character_class: str
    ability_scores: dict[str, int]
    max_hp: int
    current_hp: int
    armor_class: int
    speed: int


async def _finalize_character(
    db: AsyncSession, *, campaign_id: uuid.UUID, actor_id: uuid.UUID, body: FinalizeCharacterIn
) -> CharacterSheet:
    """Flush-only, never commits — same convention chain/service.py's/chain/seed_service.py's
    functions follow, so the db_session test fixture's rollback-based isolation holds
    (committing here would leak test data into the dev DB, the exact bug caught and fixed
    once already in commit_seed during Phase 3B). The route below commits."""
    ancestry = (
        await db.execute(
            select(AncestryDef).where(AncestryDef.campaign_id == campaign_id, AncestryDef.key == body.ancestry_key)
        )
    ).scalar_one_or_none()
    if not ancestry:
        raise HTTPException(status_code=404, detail=f"ancestry {body.ancestry_key!r} not found")

    class_def = (
        await db.execute(
            select(ClassDef).where(ClassDef.campaign_id == campaign_id, ClassDef.key == body.class_key)
        )
    ).scalar_one_or_none()
    if not class_def:
        raise HTTPException(status_code=404, detail=f"class {body.class_key!r} not found")

    if body.method == "point_buy":
        if any(score < 8 or score > 15 for score in body.ability_scores.values()):
            raise HTTPException(status_code=400, detail="point-buy scores must each be between 8 and 15")
        cost = point_buy_cost(body.ability_scores)
        if cost > POINT_BUY_POOL:
            raise HTTPException(
                status_code=400, detail=f"point-buy cost {cost} exceeds pool of {POINT_BUY_POOL}"
            )

    sheet = (
        await db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id))
    ).scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=404, detail="character sheet not found for this actor")

    con_score = body.ability_scores.get("con", 10)
    dex_score = body.ability_scores.get("dex", 10)
    max_hp = max(1, class_def.hit_die + ability_mod(con_score))
    armor_class = 10 + ability_mod(dex_score)

    sheet.ancestry = ancestry.name
    sheet.character_class = class_def.name
    sheet.ability_scores = body.ability_scores
    sheet.proficiencies = class_def.proficiencies
    sheet.max_hp = max_hp
    sheet.current_hp = max_hp
    sheet.armor_class = armor_class
    sheet.speed = ancestry.speed
    await db.flush()
    return sheet


@router.get("/{campaign_id}/actors/{actor_id}/sheet")
async def get_character_sheet(campaign_id: uuid.UUID, actor_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Feeds the frontend's character-sheet/status HUD (see the "Real Mechanical
    Consequences" plan) — the ability scores/hp/ac/conditions/inventory a live-playing
    character actually has right now, distinct from get_character_options (the pre-creation
    catalog of what's available to choose from)."""
    sheet = (
        await db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id))
    ).scalar_one_or_none()
    if not sheet:
        raise HTTPException(status_code=404, detail="character sheet not found for this actor")

    rows = (
        await db.execute(
            select(InventoryItem, ItemDef)
            .join(ItemDef, ItemDef.id == InventoryItem.item_def_id)
            .where(InventoryItem.owner_actor_id == actor_id)
        )
    ).all()

    return {
        "ancestry": sheet.ancestry,
        "character_class": sheet.character_class,
        "level": sheet.level,
        "ability_scores": sheet.ability_scores,
        "max_hp": sheet.max_hp,
        "current_hp": sheet.current_hp,
        "armor_class": sheet.armor_class,
        "speed": sheet.speed,
        "conditions": sheet.conditions,
        "inventory": [
            {
                "item_def_id": str(item.id), "name": item.name, "item_type": item.item_type,
                "quantity": inv.quantity, "equipped": inv.equipped,
            }
            for inv, item in rows
        ],
    }


@router.post("/{campaign_id}/actors/{actor_id}/finalize-character", response_model=FinalizeCharacterOut)
async def finalize_character(
    campaign_id: uuid.UUID, actor_id: uuid.UUID, body: FinalizeCharacterIn, db: AsyncSession = Depends(get_db)
) -> FinalizeCharacterOut:
    sheet = await _finalize_character(db, campaign_id=campaign_id, actor_id=actor_id, body=body)
    await db.commit()

    return FinalizeCharacterOut(
        actor_id=actor_id,
        ancestry=sheet.ancestry,
        character_class=sheet.character_class,
        ability_scores=sheet.ability_scores,
        max_hp=sheet.max_hp,
        current_hp=sheet.current_hp,
        armor_class=sheet.armor_class,
        speed=sheet.speed,
    )
