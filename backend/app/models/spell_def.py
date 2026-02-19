from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, JSON
from app.db.base import Base

class SpellDef(Base):
    __tablename__ = "spell_defs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    name: Mapped[str] = mapped_column(String(200), index=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    school: Mapped[str] = mapped_column(String(64), default="universal")

    range: Mapped[str] = mapped_column(String(64), default="self")
    duration: Mapped[str] = mapped_column(String(64), default="instant")
    components: Mapped[str] = mapped_column(String(64), default="V,S")

    effect: Mapped[dict] = mapped_column(JSON, default=dict)

    # reskin fields
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
