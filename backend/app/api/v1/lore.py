from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lore_document import LoreDocument
from app.services.lore.indexer import index_lore_document
from app.services.lore.retriever import retrieve_lore_chunks
from app.services.llm.roles import get_llm


router = APIRouter()


class LoreDocCreate(BaseModel):
    campaign_id: str
    title: str
    doc_type: str = "world"
    status: str = "canon"
    content_markdown: str = ""
    tags: list[str] = Field(default_factory=list)


class LoreDocUpdate(BaseModel):
    title: str | None = None
    doc_type: str | None = None
    status: str | None = None
    content_markdown: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


@router.get("/campaigns/{campaign_id}/lore-docs")
def list_lore_docs(campaign_id: str, db: Session = Depends(get_db)):
    docs = (
        db.execute(
            select(LoreDocument)
            .where(LoreDocument.campaign_id == campaign_id)
            .order_by(LoreDocument.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": d.id,
            "campaign_id": d.campaign_id,
            "title": d.title,
            "doc_type": d.doc_type,
            "status": d.status,
            "version": d.version,
            "tags": d.tags,
            "is_active": d.is_active,
            "updated_at": d.updated_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/lore-docs/{doc_id}")
def get_lore_doc(doc_id: str, db: Session = Depends(get_db)):
    d = db.execute(select(LoreDocument).where(LoreDocument.id == doc_id)).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": d.id,
        "campaign_id": d.campaign_id,
        "title": d.title,
        "doc_type": d.doc_type,
        "status": d.status,
        "version": d.version,
        "tags": d.tags,
        "content_markdown": d.content_markdown,
        "is_active": d.is_active,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


@router.post("/lore-docs")
def create_lore_doc(req: LoreDocCreate, db: Session = Depends(get_db)):
    d = LoreDocument(
        campaign_id=req.campaign_id,
        title=req.title,
        doc_type=req.doc_type,
        status=req.status,
        content_markdown=req.content_markdown,
        tags=req.tags,
        source="gm",
    )
    db.add(d)
    db.commit()
    return {"id": d.id}


@router.patch("/lore-docs/{doc_id}")
def update_lore_doc(doc_id: str, req: LoreDocUpdate, db: Session = Depends(get_db)):
    d = db.execute(select(LoreDocument).where(LoreDocument.id == doc_id)).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="not_found")
    data = req.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(d, k, v)
    if "content_markdown" in data:
        d.version = int(d.version or 1) + 1
    db.commit()
    return {"status": "ok"}


@router.post("/lore-docs/{doc_id}/reindex")
def reindex_doc(doc_id: str, db: Session = Depends(get_db)):
    d = db.execute(select(LoreDocument).where(LoreDocument.id == doc_id)).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="not_found")
    llm = get_llm()
    n = index_lore_document(db, llm=llm, doc=d)
    db.commit()
    return {"chunks": n}


@router.get("/campaigns/{campaign_id}/retrieve")
def retrieve(campaign_id: str, query: str, db: Session = Depends(get_db)):
    llm = get_llm()
    hits = retrieve_lore_chunks(db, llm=llm, campaign_id=campaign_id, query=query)
    return {"hits": hits}
