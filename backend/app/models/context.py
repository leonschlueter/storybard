from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Float, JSON, Boolean

from app.db.base import Base

class ContextBlock(Base):
    __tablename__ = "context_blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    type: Mapped[str] = mapped_column(String(64), index=True)   # memory, location, npc, thread, mechanic, campaign_summary, etc
    title: Mapped[str] = mapped_column(String(240), index=True)

    scope_type: Mapped[str] = mapped_column(String(64), default="global")  # global|actor|location|thread
    scope_id: Mapped[str | None] = mapped_column(String, nullable=True)

    visibility: Mapped[str] = mapped_column(String(32), default="player")  # player|gm_only (future)
    hardness: Mapped[str] = mapped_column(String(16), default="soft")      # soft|hard

    summary: Mapped[str] = mapped_column(Text, default="")
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured: Mapped[dict] = mapped_column(JSON, default=dict)

    priority: Mapped[float] = mapped_column(Float, default=0.5)
    ttl_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
