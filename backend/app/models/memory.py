from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Index

from app.db.base import Base


class Memory(Base):
    """A short, searchable memory snippet.

    - owner_actor_id: who holds this memory (PC or NPC)
    - subject_actor_id: optional, who this memory is about
    """

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    owner_actor_id: Mapped[str] = mapped_column(String, ForeignKey("actors.id"), index=True)
    subject_actor_id: Mapped[str | None] = mapped_column(String, ForeignKey("actors.id"), nullable=True, index=True)

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(Text)

    importance: Mapped[int] = mapped_column(Integer, default=1)  # 1..5
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index(
    "ix_memories_campaign_owner_subject",
    Memory.campaign_id,
    Memory.owner_actor_id,
    Memory.subject_actor_id,
)
