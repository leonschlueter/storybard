from __future__ import annotations

import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class SpellDef(Base):
    """Campaign-scoped spell definition. See spec.md "Entity creation"."""

    __tablename__ = "spell_defs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=0)  # 0 = cantrip
    school: Mapped[str] = mapped_column(String(32))
    casting_time: Mapped[str] = mapped_column(String(64))
    range: Mapped[str] = mapped_column(String(64))
    duration: Mapped[str] = mapped_column(String(64))
    effect: Mapped[str] = mapped_column(Text)


# Fields match CreateSpellDefOp's constructor kwargs one-to-one (minus "op") — the
# "standard_5e" seeding fast path (chain/seed_service.py) builds ops directly from these,
# no LLM call needed.
DEFAULT_5E_SPELLS: list[dict] = [
    {
        "name": "Fire Bolt", "description": "A mote of fire hurled at a target.", "level": 0,
        "school": "evocation", "casting_time": "1 action", "range": "120 feet",
        "duration": "instantaneous", "effect": "1d10 fire damage on a ranged spell attack hit.",
    },
    {
        "name": "Magic Missile", "description": "Darts of magical force strike unerringly.", "level": 1,
        "school": "evocation", "casting_time": "1 action", "range": "120 feet",
        "duration": "instantaneous", "effect": "Three darts, each dealing 1d4+1 force damage, auto-hit.",
    },
    {
        "name": "Cure Wounds", "description": "A touch that mends wounds.", "level": 1,
        "school": "evocation", "casting_time": "1 action", "range": "touch",
        "duration": "instantaneous", "effect": "Heals 1d8 + spellcasting modifier hit points.",
    },
    {
        "name": "Mage Armor", "description": "A protective magical field.", "level": 1,
        "school": "abjuration", "casting_time": "1 action", "range": "touch",
        "duration": "8 hours", "effect": "Target's AC becomes 13 + DEX modifier while unarmored.",
    },
]
