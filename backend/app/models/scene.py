from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, JSON, Boolean, DateTime, ForeignKey

from app.db.base import Base


class Scene(Base):
    """Current Scene (prototype-friendly, Friends & Fables style).

    There can be multiple scenes, but exactly one should be is_current=True.
    """

    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    title: Mapped[str] = mapped_column(String(200), default="Current Scene")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    current_node_id: Mapped[str | None] = mapped_column(String, ForeignKey("world_nodes.id"), nullable=True)

    # lists of ids for quick UI composition
    npc_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    # arbitrary panel text (world info, nearby locations, etc.)
    world_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    nearby_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
