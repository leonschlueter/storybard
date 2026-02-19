from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.thread import StoryThread

def list_threads(db: Session, campaign_id: str) -> list[StoryThread]:
    return db.execute(select(StoryThread).where(StoryThread.campaign_id == campaign_id)).scalars().all()
