from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import get_db
from app.models.context import ContextBlock
from app.schemas.api import ContextBlockUpdate

router = APIRouter()

@router.put("/context-blocks/{block_id}")
def update_block(block_id: str, patch: ContextBlockUpdate, db: Session = Depends(get_db)):
    b = db.execute(select(ContextBlock).where(ContextBlock.id == block_id)).scalar_one_or_none()
    if not b:
        return {"error":"not_found"}

    data = patch.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(b, k, v)
    db.commit()
    return {"ok": True, "id": b.id}
