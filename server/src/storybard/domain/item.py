from __future__ import annotations

import uuid

from sqlalchemy import JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class ItemDef(Base):
    """Campaign-scoped item definition (weapon, armor, gear, consumable...). Damage dice,
    AC bonus, weight, cost etc. all live in the freeform `properties` dict rather than
    fixed columns per item type, matching Faction.goals's existing JSON-blob precedent.
    See spec.md "Entity creation."
    """

    __tablename__ = "item_defs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    key: Mapped[str] = mapped_column(String(64))  # stable internal id, e.g. "longsword"
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(32))  # weapon | armor | gear | consumable | ...
    properties: Mapped[dict] = mapped_column(JSON, default=dict)


# Fields match CreateItemDefOp's constructor kwargs one-to-one (minus "op") — the
# "standard_5e" seeding fast path (chain/seed_service.py) builds ops directly from these,
# no LLM call needed.
DEFAULT_5E_ITEMS: list[dict] = [
    {
        "key": "longsword", "name": "Longsword", "description": "A versatile blade.",
        "item_type": "weapon", "properties": {"damage": "1d8 slashing", "weight_lb": 3},
    },
    {
        "key": "shortbow", "name": "Shortbow", "description": "A simple ranged weapon.",
        "item_type": "weapon", "properties": {"damage": "1d6 piercing", "range_ft": 80},
    },
    {
        "key": "leather_armor", "name": "Leather Armor", "description": "Light, flexible armor.",
        "item_type": "armor", "properties": {"ac_bonus": 1, "weight_lb": 10},
    },
    {
        "key": "shield", "name": "Shield", "description": "A sturdy wooden shield.",
        "item_type": "armor", "properties": {"ac_bonus": 2, "weight_lb": 6},
    },
    {
        "key": "healing_potion", "name": "Healing Potion", "description": "Restores health when drunk.",
        "item_type": "consumable", "properties": {"heals": "2d4+2"},
    },
]
