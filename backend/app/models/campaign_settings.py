from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, JSON, DateTime, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CampaignSettings(Base):
    """Highly customizable knobs for ruleset + narrative behavior.

    Keep most settings flexible via JSON, but also store a few frequently-used knobs.
    """

    __tablename__ = "campaign_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True, unique=True)

    # Ruleset / tech
    ruleset: Mapped[str] = mapped_column(String(64), default="dnd5e")
    tech_level: Mapped[str] = mapped_column(String(64), default="fantasy_medieval")
    magic_level: Mapped[str] = mapped_column(String(32), default="medium")

    # Prompt behavior
    narrator_verbosity: Mapped[float] = mapped_column(Float, default=0.7)  # 0..1
    director_verbosity: Mapped[float] = mapped_column(Float, default=0.6)

    # Scene defaults
    scene_npc_limit: Mapped[int] = mapped_column(Integer, default=2)

    # Summarizer
    summarize_every_n_turns: Mapped[int] = mapped_column(Integer, default=6)

    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
