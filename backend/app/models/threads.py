import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class Faction(Base):
    __tablename__ = "factions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)

    name: Mapped[str] = mapped_column(String(200), index=True)
    influence: Mapped[int] = mapped_column(Integer, default=0)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)

    thread_type: Mapped[str] = mapped_column(String(50), index=True)  # political/magical/etc
    status: Mapped[str] = mapped_column(String(30), index=True, default="active")

    region_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_nodes.id"), nullable=True, index=True)

    current_stage: Mapped[int] = mapped_column(Integer, default=1)
    momentum: Mapped[int] = mapped_column(Integer, default=0)
    visibility: Mapped[int] = mapped_column(Integer, default=0)   # 0-100
    threat_level: Mapped[int] = mapped_column(Integer, default=0) # 0-100

    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)
