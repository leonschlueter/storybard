import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import Base


class WorldNode(Base):
    __tablename__ = "world_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_nodes.id"), nullable=True)

    node_type: Mapped[str] = mapped_column(String(50), index=True)  # see NodeType enum
    name: Mapped[str] = mapped_column(String(200))

    simulation_level: Mapped[int] = mapped_column(Integer, default=3)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)

    parent = relationship("WorldNode", remote_side=[id])


class WorldEdge(Base):
    __tablename__ = "world_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)

    from_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("world_nodes.id"), index=True)
    to_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("world_nodes.id"), index=True)

    travel_time: Mapped[int] = mapped_column(Integer, default=10)  # minutes/ticks
    travel_risk: Mapped[int] = mapped_column(Integer, default=0)   # 0-100 arbitrary
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)
