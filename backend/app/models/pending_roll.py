from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, JSON, DateTime
from datetime import datetime
from app.db.base import Base

class PendingRoll(Base):
    __tablename__ = "pending_rolls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String, index=True)

    roll_type: Mapped[str] = mapped_column(String(32))  # skill_check | initiative
    skill: Mapped[str | None] = mapped_column(String(64), nullable=True)

    dc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dc_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # player action that triggered this roll
    action_text: Mapped[str] = mapped_column(String(2000))
    intent: Mapped[dict] = mapped_column(JSON, default=dict)

    # precomputed modifier details
    modifier: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    d20: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)  # success/fail/crit_success/crit_fail

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
