from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


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

    # Needed for "most important, then most recent" ordering (context_assembly.py's
    # build_relevant_memories) — a UUIDv4 id is not chronological, so there was previously
    # no way to express recency at all.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
