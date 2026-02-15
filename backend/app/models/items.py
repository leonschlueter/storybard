import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db.base import Base


class ItemDefinition(Base):
    __tablename__ = "item_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), index=True)
    item_type: Mapped[str] = mapped_column(String(50), index=True)  # weapon/armor/gear/consumable/etc
    rarity: Mapped[str] = mapped_column(String(50), default="common")

    base_properties: Mapped[dict] = mapped_column(JSONB, default=dict)


class ItemInstance(Base):
    __tablename__ = "item_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)

    definition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("item_definitions.id"), index=True)

    owner_actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True, index=True)
    location_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_nodes.id"), nullable=True, index=True)

    equipped_slot: Mapped[str | None] = mapped_column(String(50), nullable=True)  # weapon_main, armor, etc

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    custom_properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)
