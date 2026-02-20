from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.context import ContextBlock


router = APIRouter()


class ContextBlockCreateIn(BaseModel):
    type: str = Field(default="misc")
    title: str = Field(default="")
    summary: str = Field(default="")
    full_text: str | None = None
    structured: dict | None = None

    scope_type: str | None = None
    scope_id: str | None = None

    visibility: str = Field(default="player")
    hardness: str = Field(default="soft")
    priority: float = Field(default=0.6, ge=0.0, le=1.0)
    ttl_turns: int | None = None
    is_active: bool = True


class ContextBlockUpdateIn(BaseModel):
    type: str | None = None
    title: str | None = None
    summary: str | None = None
    full_text: str | None = None
    structured: dict | None = None
    priority: float | None = Field(default=None, ge=0.0, le=1.0)
    ttl_turns: int | None = None
    is_active: bool | None = None
    visibility: str | None = None
    hardness: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None

    # compatibility
    text: str | None = None


def _serialize(b: ContextBlock) -> dict:
    return {
        "id": b.id,
        "campaign_id": b.campaign_id,
        "type": b.type,
        "title": b.title,
        "summary": b.summary,
        "full_text": b.full_text,
        "structured": b.structured,
        "scope_type": b.scope_type,
        "scope_id": b.scope_id,
        "visibility": b.visibility,
        "hardness": b.hardness,
        "priority": b.priority,
        "ttl_turns": b.ttl_turns,
        "is_active": b.is_active,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


@router.get("/context_blocks/{campaign_id}")
@router.get("/campaigns/{campaign_id}/context-blocks")
def list_context_blocks(campaign_id: str, db: Session = Depends(get_db)):
    blocks = (
        db.execute(
            select(ContextBlock)
            .where(ContextBlock.campaign_id == campaign_id)
            .order_by(ContextBlock.type.asc(), ContextBlock.priority.desc())
        )
        .scalars()
        .all()
    )
    return [_serialize(b) for b in blocks]


@router.post("/context_blocks/{campaign_id}")
def create_context_block(campaign_id: str, data: ContextBlockCreateIn, db: Session = Depends(get_db)):
    b = ContextBlock(
        campaign_id=campaign_id,
        type=data.type,
        title=data.title,
        summary=data.summary,
        full_text=data.full_text,
        structured=data.structured,
        scope_type=data.scope_type,
        scope_id=data.scope_id,
        visibility=data.visibility,
        hardness=data.hardness,
        priority=data.priority,
        ttl_turns=data.ttl_turns,
        is_active=data.is_active,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return {"status": "ok", "block": _serialize(b)}


@router.put("/context_blocks/{block_id}")
@router.put("/context-blocks/{block_id}")
def update_context_block(block_id: str, data: ContextBlockUpdateIn, db: Session = Depends(get_db)):
    b = db.execute(select(ContextBlock).where(ContextBlock.id == block_id)).scalar_one_or_none()
    if not b:
        return {"status": "error", "error": "not_found"}

    # compatibility
    if data.text and not data.summary:
        data.summary = data.text

    for field in (
        "type",
        "title",
        "summary",
        "full_text",
        "structured",
        "priority",
        "ttl_turns",
        "is_active",
        "visibility",
        "hardness",
        "scope_type",
        "scope_id",
    ):
        v = getattr(data, field)
        if v is not None:
            setattr(b, field, v)

    db.commit()
    db.refresh(b)
    return {"status": "ok", "block": _serialize(b)}
