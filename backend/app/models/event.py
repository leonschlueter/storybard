from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, JSON, DateTime
from datetime import datetime
from app.db.base import Base

class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String, index=True)

    campaign_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mode: Mapped[str] = mapped_column(String(32), default="explore")

    action_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[dict] = mapped_column(JSON, default=dict)

    check: Mapped[dict] = mapped_column(JSON, default=dict)       # if any (dc, skill, roll, total, outcome)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)

    result_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
