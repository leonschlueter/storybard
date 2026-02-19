from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Float, DateTime, JSON
from datetime import datetime
from app.db.base import Base

class StoryThread(Base):
    __tablename__ = "story_threads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    title: Mapped[str] = mapped_column(String(200), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active/completed/failed
    priority: Mapped[float] = mapped_column(Float, default=0.5)

    state: Mapped[dict] = mapped_column(JSON, default=dict)  # arbitrary structured state
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
