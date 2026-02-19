from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.context import ContextBlock
from app.models.event import Event

def last_n_events(db: Session, campaign_id: str, n: int) -> list[dict]:
    evs = db.execute(
        select(Event).where(Event.campaign_id == campaign_id).order_by(Event.created_at.desc()).limit(n)
    ).scalars().all()
    evs = list(reversed(evs))
    return [{"action_text": e.action_text, "narration": e.narration, "check": e.check} for e in evs]

def get_campaign_summary_block(db: Session, campaign_id: str) -> ContextBlock | None:
    return db.execute(
        select(ContextBlock).where(ContextBlock.campaign_id == campaign_id, ContextBlock.type == "campaign_summary")
    ).scalar_one_or_none()
