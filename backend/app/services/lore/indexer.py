from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lore_chunk import LoreChunk
from app.models.lore_document import LoreDocument
from app.services.llm.roles import LLMRoles
from app.services.lore.chunker import chunk_markdown


def index_lore_document(db: Session, *, llm: LLMRoles, doc: LoreDocument) -> int:
    """(Re)index a lore document into LoreChunk rows."""
    # delete existing
    db.execute(delete(LoreChunk).where(LoreChunk.lore_document_id == doc.id))
    db.flush()

    chunks = chunk_markdown(doc.content_markdown)
    if not chunks:
        return 0

    embed_model = settings.OLLAMA_EMBED_MODEL
    created = 0
    for ch in chunks:
        vec = llm.client.embed(model=embed_model, text=ch.text)
        db.add(
            LoreChunk(
                campaign_id=doc.campaign_id,
                lore_document_id=doc.id,
                chunk_index=ch.idx,
                chunk_text=ch.text,
                metadata={"doc_type": doc.doc_type, "tags": doc.tags, "title": doc.title},
                embedding=vec,
            )
        )
        created += 1
    db.flush()
    return created
