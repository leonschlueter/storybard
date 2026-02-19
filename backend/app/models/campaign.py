from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, JSON
from app.db.base import Base
from app.utils.enums import CampaignMode

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), index=True)

    mode: Mapped[str] = mapped_column(String(32), default=CampaignMode.explore.value)
    narration_style: Mapped[str] = mapped_column(String(64), default="basic_fantasy")

    tone_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    reskin_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    setting_tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    calendar_name: Mapped[str] = mapped_column(String(128), default="Gregorian")
    start_datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    current_datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    turn_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
