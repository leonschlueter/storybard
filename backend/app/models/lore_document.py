from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, JSON, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoreDocument(Base):
    """Long-form canon and living lore.

    Stored as markdown and versioned. Retrieval uses LoreChunk embeddings.
    """

    __tablename__ = "lore_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    title: Mapped[str] = mapped_column(String(240), index=True)
    doc_type: Mapped[str] = mapped_column(String(64), index=True, default="world")
    status: Mapped[str] = mapped_column(String(32), index=True, default="canon")  # canon|draft|deprecated

    version: Mapped[int] = mapped_column(Integer, default=1)
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), default="llm")  # llm|seed|player|gm

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
