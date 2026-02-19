from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.world import WorldNode
from app.models.actor import Actor
from app.models.lore import LorePage
from app.models.context import ContextBlock
from app.models.thread import StoryThread
from app.models.item_def import ItemDef
from app.models.spell_def import SpellDef

def fetch_selected(db: Session, selection: dict) -> dict:
    out = {"world_nodes": [], "actors": [], "lore_pages": [], "context_blocks": [], "threads": [], "item_defs": [], "spell_defs": []}

    if selection.get("world_nodes"):
        xs = db.execute(select(WorldNode).where(WorldNode.id.in_(selection["world_nodes"]))).scalars().all()
        out["world_nodes"] = [{"id": x.id, "name": x.name, "description": x.description, "x": x.x, "y": x.y} for x in xs]

    if selection.get("actors"):
        xs = db.execute(select(Actor).where(Actor.id.in_(selection["actors"]))).scalars().all()
        out["actors"] = [{"id": x.id, "name": x.name, "kind": x.kind, "bio": x.bio, "current_node_id": x.current_node_id} for x in xs]

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
