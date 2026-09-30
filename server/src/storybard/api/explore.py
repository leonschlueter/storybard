from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.core.db import get_db
from storybard.domain.faction import Faction
from storybard.domain.hook import Hook
from storybard.domain.item import ItemDef
from storybard.domain.spell import SpellDef
from storybard.domain.world import WorldNode
from storybard.services.context_assembly import (
    build_active_threads,
    build_known_actors,
    build_recent_world_events,
    project_active_threads,
)

router = APIRouter(prefix="/campaigns", tags=["explore"])

# Read-only "codex" panel per spec.md's roadmap — reuses context_assembly.py's existing
# actors/threads catalog builders verbatim. Locations get their own query here rather than
# reusing build_known_locations: that function's context-budget shape (full detail only
# for the *current* node, names-only elsewhere) exists to keep LLM prompts small — the
# opposite of what a human browsing a codex panel wants, which is every location's actual
# description. Items/spells/factions follow the same flat-list-of-dicts shape as
# api/party.py::get_character_options.


@router.get("/{campaign_id}/world-state")
async def get_world_state(campaign_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    active_threads_rows = await build_active_threads(db, campaign_id=campaign_id)
    known_actors = await build_known_actors(db, campaign_id=campaign_id)

    nodes = (await db.execute(select(WorldNode).where(WorldNode.campaign_id == campaign_id))).scalars().all()
    items = (await db.execute(select(ItemDef).where(ItemDef.campaign_id == campaign_id))).scalars().all()
    spells = (await db.execute(select(SpellDef).where(SpellDef.campaign_id == campaign_id))).scalars().all()
    factions = (await db.execute(select(Faction).where(Faction.campaign_id == campaign_id))).scalars().all()
    hooks = (await db.execute(select(Hook).where(Hook.campaign_id == campaign_id))).scalars().all()
    # Consequence ledger (feature #14) — what World Update actually committed recently,
    # surfaced to the player directly rather than only fed silently into the Narrator's
    # prompt. Reuses build_recent_world_events verbatim; a slightly larger limit than the
    # Narrator's own (3) since a human browsing a panel can take in more at once.
    recent_world_events = await build_recent_world_events(db, campaign_id=campaign_id, limit=8)

    return {
        "actors": known_actors,
        "locations": [
            {"id": str(n.id), "name": n.name, "scale": n.scale, "description": n.description} for n in nodes
        ],
        "threads": project_active_threads(active_threads_rows),
        "items": [{"id": str(i.id), "name": i.name, "item_type": i.item_type, "description": i.description} for i in items],
        "spells": [
            {
                "id": str(s.id), "name": s.name, "level": s.level, "school": s.school,
                "description": s.description, "casting_time": s.casting_time, "range": s.range,
                "duration": s.duration, "effect": s.effect,
            }
            for s in spells
        ],
        "factions": [{"id": str(f.id), "name": f.name, "description": f.description} for f in factions],
        "hooks": [
            {"id": str(h.id), "origin": h.origin, "proposed_text": h.proposed_text, "status": h.status} for h in hooks
        ],
        "recent_world_events": recent_world_events,
    }
