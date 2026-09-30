from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class InventoryItem(Base):
    """A real item instance an actor actually carries — distinct from ItemDef (the
    template/definition). spec.md's World section named this concept; nothing ever
    instantiated it, so seeded ItemDefs sat unused until an actor "picked one up" only in
    prose. See chain/seed_service.py's starting-inventory seeding and the "All 20
    Features" plan.
    """

    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    owner_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), index=True)
    item_def_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("item_defs.id"), index=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
