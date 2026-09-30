from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base

# text-embedding-nomic-embed-text-v1.5 (core/config.py::LM_STUDIO_EMBED_MODEL) — fixed at
# 768 dims, confirmed against the live LM Studio server. Changing embedding models later
# means a migration to resize this column and re-embedding every existing row.
EMBEDDING_DIM = 768


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Memory(Base):
    """A short, searchable memory snippet owned by an actor. Single source of truth for
    "what does this actor remember" — v1 had this competing with a generic context-card
    table for the same concept; that duplication doesn't exist here. See spec.md.
    """

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    owner_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), index=True)
    subject_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True, index=True
    )

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer, default=1)  # 1..5

    # Embedding of `text`, for real semantic retrieval (services/context_assembly.py's
    # build_relevant_memories) instead of a blind importance/recency sort. pgvector was
    # already in the Docker image and LMStudioClient.embed() already existed — neither was
    # ever wired to anything before this. Nullable: rows written before this column existed
    # have none; NULL sorts last under Postgres's default NULLS LAST on an ASC distance
    # ordering, so they degrade to "least relevant" rather than breaking the query.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    # Needed for "most important, then most recent" ordering (context_assembly.py's
    # build_relevant_memories) — a UUIDv4 id is not chronological, so there was previously
    # no way to express recency at all.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
