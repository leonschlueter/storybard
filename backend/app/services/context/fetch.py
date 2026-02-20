from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.world import WorldNode
from app.models.actor import Actor
from app.models.actor_profile import ActorProfile
from app.models.lore import LorePage
from app.models.context import ContextBlock
from app.models.thread import StoryThread
from app.models.item_def import ItemDef
from app.models.spell_def import SpellDef

def fetch_selected(db: Session, selection: dict) -> dict:
    out = {"world_nodes": [], "actors": [], "lore_pages": [], "context_blocks": [], "threads": [], "item_defs": [], "spell_defs": []}

    if selection.get("world_nodes"):
        xs = db.execute(select(WorldNode).where(WorldNode.id.in_(selection["world_nodes"]))).scalars().all()
        out["world_nodes"] = [{"id": x.id, "name": x.name, "description": x.description, "description_long": x.description_long, "region": x.region, "biome": x.biome, "danger_level": x.danger_level, "x": x.x, "y": x.y} for x in xs]

    if selection.get("actors"):
        xs = db.execute(select(Actor).where(Actor.id.in_(selection["actors"]))).scalars().all()
        ids = [x.id for x in xs]
        profs = db.execute(select(ActorProfile).where(ActorProfile.actor_id.in_(ids))).scalars().all() if ids else []
        prof_map = {p.actor_id: p for p in profs}
        out["actors"] = []
        for x in xs:
            p = prof_map.get(x.id)
            out["actors"].append(
                {
                    "id": x.id,
                    "name": x.name,
                    "kind": x.kind,
                    "bio": x.bio,
                    "current_node_id": x.current_node_id,
                    "profile": {
                        "pronouns": p.pronouns if p else None,
                        "voice": p.voice if p else None,
                        "faction": p.faction if p else None,
                        "appearance": p.appearance if p else None,
                        "personality": p.personality if p else None,
                        "mannerisms": p.mannerisms if p else None,
                        "backstory": p.backstory if p else None,
                        "goals": p.goals if p else None,
                        "secrets": p.secrets if p else None,
                        "extra": p.extra if p else {},
                    },
                }
            )

    if selection.get("lore_pages"):
        xs = db.execute(select(LorePage).where(LorePage.id.in_(selection["lore_pages"]))).scalars().all()
        out["lore_pages"] = [{"id": x.id, "title": x.title, "summary": x.summary, "content": x.content, "tags": x.tags} for x in xs]

    if selection.get("context_blocks"):
        xs = db.execute(select(ContextBlock).where(ContextBlock.id.in_(selection["context_blocks"]))).scalars().all()
        out["context_blocks"] = [{"id": x.id, "type": x.type, "title": x.title, "scope_type": x.scope_type, "scope_id": x.scope_id, "summary": x.summary, "full_text": x.full_text, "structured": x.structured, "priority": x.priority, "ttl_turns": x.ttl_turns} for x in xs]

    if selection.get("threads"):
        xs = db.execute(select(StoryThread).where(StoryThread.id.in_(selection["threads"]))).scalars().all()
        out["threads"] = [{"id": x.id, "title": x.title, "summary": x.summary, "status": x.status, "priority": x.priority, "state": x.state} for x in xs]

    if selection.get("item_defs"):
        xs = db.execute(select(ItemDef).where(ItemDef.id.in_(selection["item_defs"]))).scalars().all()
        out["item_defs"] = [{"id": x.id, "name": x.name, "base_type": x.base_type, "rarity": x.rarity, "weight": x.weight, "effect": x.effect, "display_name": x.display_name, "display_description": x.display_description, "visual_tags": x.visual_tags} for x in xs]

    if selection.get("spell_defs"):
        xs = db.execute(select(SpellDef).where(SpellDef.id.in_(selection["spell_defs"]))).scalars().all()
        out["spell_defs"] = [{"id": x.id, "name": x.name, "level": x.level, "school": x.school, "range": x.range, "duration": x.duration, "components": x.components, "effect": x.effect, "display_name": x.display_name, "display_description": x.display_description, "visual_tags": x.visual_tags} for x in xs]

    return out
