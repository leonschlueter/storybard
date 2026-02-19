from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.context import ContextBlock

def decay_ttl_blocks(db: Session, campaign_id: str) -> int:
    blocks = db.execute(
        select(ContextBlock).where(ContextBlock.campaign_id == campaign_id, ContextBlock.is_active == True)
    ).scalars().all()
    changed = 0
    for b in blocks:
        if b.ttl_turns is not None:
            b.ttl_turns -= 1
            changed += 1
            if b.ttl_turns <= 0:
                b.is_active = False
    return changed
