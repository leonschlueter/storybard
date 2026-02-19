from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey
from app.db.base import Base
from app.utils.enums import ActorKind

class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(String, index=True)

    name: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=ActorKind.npc.value)

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    current_node_id: Mapped[str | None] = mapped_column(String, ForeignKey("world_nodes.id"), nullable=True)
