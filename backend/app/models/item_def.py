from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Float, JSON
from app.db.base import Base

class ItemDef(Base):
    __tablename__ = "item_defs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    base_type: Mapped[str] = mapped_column(String(64), default="generic")
    name: Mapped[str] = mapped_column(String(160), index=True)

    # mechanical fields
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    rarity: Mapped[str] = mapped_column(String(32), default="common")
    effect: Mapped[dict] = mapped_column(JSON, default=dict)  # mechanical effects schema

    # reskin fields (unused by mechanics for now)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    display_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
