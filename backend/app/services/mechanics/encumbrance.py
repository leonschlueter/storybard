from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.inventory import InventoryItem
from app.models.item_def import ItemDef
from app.models.character_sheet import CharacterSheet
from app.services.mechanics.modifiers import ability_mod

def compute_carried_weight(db: Session, actor_id: str) -> float:
    items = db.execute(select(InventoryItem).where(InventoryItem.actor_id == actor_id)).scalars().all()
    total = 0.0
    for inv in items:
        item = db.execute(select(ItemDef).where(ItemDef.id == inv.item_def_id)).scalar_one_or_none()
        if not item:
            continue
        total += float(item.weight) * int(inv.quantity)
    return total

def encumbrance_snapshot(db: Session, actor_id: str) -> dict:
    sheet = db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id)).scalar_one_or_none()
    if not sheet:
        return {"encumbered": False, "carried_weight": 0.0, "max_weight": None, "speed_effective": None}

    scores = sheet.ability_scores or {}
    str_score = int(scores.get("STR", 10))
    max_weight = str_score * 15
    carried = compute_carried_weight(db, actor_id)
    enc = carried > max_weight

    speed_eff = sheet.speed
    if enc:
        # simple penalty for now; you can refine later
        speed_eff = max(5, int(sheet.speed * 0.5))

    return {
        "encumbered": enc,
        "carried_weight": round(carried, 2),
        "max_weight": max_weight,
        "speed_base": sheet.speed,
        "speed_effective": speed_eff,
    }
