from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.memory import Memory


router = APIRouter()


class MemoryCreateIn(BaseModel):
    owner_actor_id: str
    subject_actor_id: str | None = None
    title: str | None = None
    text: str = Field(min_length=1, max_length=5000)
    importance: int = Field(default=1, ge=1, le=5)


@router.get("/memories/{campaign_id}/{owner_actor_id}")
def list_memories(campaign_id: str, owner_actor_id: str, db: Session = Depends(get_db)):
    mems = (
        db.execute(
            select(Memory)
            .where(Memory.campaign_id == campaign_id, Memory.owner_actor_id == owner_actor_id)
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": m.id,
            "campaign_id": m.campaign_id,
            "owner_actor_id": m.owner_actor_id,
            "subject_actor_id": m.subject_actor_id,
            "title": m.title,
            "text": m.text,
            "importance": m.importance,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in mems
    ]


@router.post("/memories/{campaign_id}")
def create_memory(campaign_id: str, data: MemoryCreateIn, db: Session = Depends(get_db)):
    m = Memory(
        campaign_id=campaign_id,
        owner_actor_id=data.owner_actor_id,
        subject_actor_id=data.subject_actor_id,
        title=data.title,
        text=data.text,
        importance=data.importance,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"status": "ok", "id": m.id}
