from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lore_chunk import LoreChunk
from app.services.llm.roles import LLMRoles


def retrieve_lore_chunks(
    db: Session,
    *,
    llm: LLMRoles,
    campaign_id: str,
    query: str,
    top_k: int | None = None,
    doc_type: str | None = None,
    tags_any: list[str] | None = None,
) -> list[dict]:
    """Semantic retrieval of lore chunks.

    Returns list of dicts: {chunk_text, title, doc_type, score}
    """
    top_k = int(top_k or settings.RETRIEVAL_TOP_K)
    qvec = llm.client.embed(model=settings.OLLAMA_EMBED_MODEL, text=query)

    stmt = select(LoreChunk, LoreChunk.embedding.cosine_distance(qvec).label("dist")).where(
        LoreChunk.campaign_id == campaign_id
    )
    if doc_type:
        stmt = stmt.where(LoreChunk.metadata["doc_type"].as_string() == doc_type)
    if tags_any:
        # metadata.tags is JSON list; keep it simple: filter later in python
        pass

    stmt = stmt.order_by("dist").limit(top_k)
    rows = db.execute(stmt).all()

    out: list[dict] = []
    for chunk, dist in rows:
        meta = chunk.meta or {}
        if tags_any:
            tags = set(meta.get("tags") or [])
            if not tags.intersection(set(tags_any)):
                continue
        out.append(
            {
                "chunk_text": chunk.chunk_text,
                "title": meta.get("title"),
                "doc_type": meta.get("doc_type"),
                "distance": float(dist or 0.0),
            }
        )
    return out
