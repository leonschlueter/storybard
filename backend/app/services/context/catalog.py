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

def build_catalogs(db: Session, campaign_id: str, limit: int = 80) -> dict:
    nodes = db.execute(select(WorldNode).where(WorldNode.campaign_id == campaign_id).limit(limit)).scalars().all()
    actors = db.execute(select(Actor).where(Actor.campaign_id == campaign_id).limit(limit)).scalars().all()
    lore = db.execute(select(LorePage).where(LorePage.campaign_id == campaign_id).limit(limit)).scalars().all()
    blocks = db.execute(select(ContextBlock).where(ContextBlock.campaign_id == campaign_id, ContextBlock.is_active == True).limit(limit)).scalars().all()
    threads = db.execute(select(StoryThread).where(StoryThread.campaign_id == campaign_id).limit(limit)).scalars().all()
    items = db.execute(select(ItemDef).where(ItemDef.campaign_id == campaign_id).limit(limit)).scalars().all()
    spells = db.execute(select(SpellDef).where(SpellDef.campaign_id == campaign_id).limit(limit)).scalars().all()

    return {
        "world_nodes": [{"id": n.id, "name": n.name} for n in nodes],
        "actors": [{"id": a.id, "name": a.name, "kind": a.kind, "current_node_id": a.current_node_id} for a in actors],
        "lore_pages": [{"id": p.id, "title": p.title, "tags": p.tags} for p in lore],
        "context_blocks": [{"id": b.id, "type": b.type, "title": b.title, "scope_type": b.scope_type, "scope_id": b.scope_id, "priority": b.priority} for b in blocks],
        "threads": [{"id": t.id, "title": t.title, "status": t.status, "priority": t.priority} for t in threads],
        "item_defs": [{"id": i.id, "name": i.name, "base_type": i.base_type, "rarity": i.rarity} for i in items],
        "spell_defs": [{"id": s.id, "name": s.name, "level": s.level, "school": s.school} for s in spells],
    }
