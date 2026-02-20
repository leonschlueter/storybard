from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, JSON, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.db.base import Base


class LoreChunk(Base):
    """Embeddable chunks for semantic retrieval."""

    __tablename__ = "lore_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    lore_document_id: Mapped[str] = mapped_column(String, ForeignKey("lore_documents.id"), index=True)

    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIM))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_lore_chunks_campaign_doc", LoreChunk.campaign_id, LoreChunk.lore_document_id)
