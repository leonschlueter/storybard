from __future__ import annotations

import uuid

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, JSON, ForeignKey

from app.db.base import Base


class ActorProfile(Base):
    """Richer NPC/PC descriptive profile.

    Keep mechanics in CharacterSheet; keep narrative/social details here.
    """

    __tablename__ = "actor_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String, ForeignKey("actors.id"), unique=True, index=True)

    pronouns: Mapped[str | None] = mapped_column(String(32), nullable=True)
    voice: Mapped[str | None] = mapped_column(String(64), nullable=True)
    faction: Mapped[str | None] = mapped_column(String(128), nullable=True)

    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    mannerisms: Mapped[str | None] = mapped_column(Text, nullable=True)
    backstory: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    secrets: Mapped[str | None] = mapped_column(Text, nullable=True)

    # arbitrary structured data for future (relationships, flags, etc.)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
