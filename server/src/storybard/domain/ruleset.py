from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class AttributeDefinition(Base):
    """Ruleset/campaign-scoped attribute (ability score) definition.

    No hardcoded STR/DEX/CON/INT/WIS/CHA columns anywhere in the system —
    CharacterSheet.ability_scores is a dict[key, int] keyed by these. The default
    5e-ish ruleset seeds the standard six as data; a different ruleset or a thematic
    reskin ("Might/Grace/Wit/Spirit") is a data change, not a schema change.
    """

    __tablename__ = "attribute_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    key: Mapped[str] = mapped_column(String(32))  # stable internal id, e.g. "str"
    display_name: Mapped[str] = mapped_column(String(64))  # e.g. "Strength" or "Might"
    abbreviation: Mapped[str] = mapped_column(String(8))  # e.g. "STR"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class AncestryDef(Base):
    """Campaign-scoped playable ancestry/race (e.g. "Elf"), same per-campaign-row pattern
    as AttributeDefinition — a different ruleset or a wholly invented fantasy world is a
    data change, not a schema change. See spec.md "Entity creation."
    """

    __tablename__ = "ancestry_defs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    key: Mapped[str] = mapped_column(String(32))  # stable internal id, e.g. "elf"
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    speed: Mapped[int] = mapped_column(Integer, default=30)
    features: Mapped[dict] = mapped_column(JSON, default=dict)  # freeform: darkvision, resistances, etc.


class ClassDef(Base):
    """Campaign-scoped playable class (e.g. "Wizard"). primary_attribute_key references an
    AttributeDefinition.key for this campaign, not a hardcoded ability — same hotswappable
    intent as ability_scores. See spec.md "Entity creation."
    """

    __tablename__ = "class_defs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    key: Mapped[str] = mapped_column(String(32))  # stable internal id, e.g. "wizard"
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hit_die: Mapped[int] = mapped_column(Integer, default=8)
    primary_attribute_key: Mapped[str] = mapped_column(String(32))
    proficiencies: Mapped[dict] = mapped_column(JSON, default=dict)
    spellcasting: Mapped[bool] = mapped_column(Boolean, default=False)
    starting_equipment: Mapped[dict] = mapped_column(JSON, default=dict)


DEFAULT_5E_ATTRIBUTES: list[dict] = [
    {"key": "str", "display_name": "Strength", "abbreviation": "STR", "sort_order": 0},
    {"key": "dex", "display_name": "Dexterity", "abbreviation": "DEX", "sort_order": 1},
    {"key": "con", "display_name": "Constitution", "abbreviation": "CON", "sort_order": 2},
    {"key": "int", "display_name": "Intelligence", "abbreviation": "INT", "sort_order": 3},
    {"key": "wis", "display_name": "Wisdom", "abbreviation": "WIS", "sort_order": 4},
    {"key": "cha", "display_name": "Charisma", "abbreviation": "CHA", "sort_order": 5},
]

# Fields here deliberately match CreateAncestryDefOp's/CreateClassDefOp's constructor
# kwargs one-to-one (minus "op") — the "standard_5e" seeding fast path (chain/seed_
# service.py) builds ops directly from these dicts, no LLM call needed. Small,
# representative sets, not an exhaustive 5e SRD reproduction.
DEFAULT_5E_ANCESTRIES: list[dict] = [
    {"key": "human", "name": "Human", "description": "Versatile and ambitious.", "speed": 30, "features": {}},
    {
        "key": "elf", "name": "Elf", "description": "Graceful and long-lived.", "speed": 30,
        "features": {"darkvision": 60, "trance": True},
    },
    {
        "key": "dwarf", "name": "Dwarf", "description": "Stout and resilient.", "speed": 25,
        "features": {"darkvision": 60, "poison_resistance": True},
    },
    {
        "key": "halfling", "name": "Halfling", "description": "Small and lucky.", "speed": 25,
        "features": {"lucky": True},
    },
]

DEFAULT_5E_CLASSES: list[dict] = [
    {
        "key": "fighter", "name": "Fighter", "description": "A master of martial combat.",
        "hit_die": 10, "primary_attribute_key": "str", "proficiencies": {"armor": "all", "weapons": "all"},
        "spellcasting": False, "starting_equipment": {"weapon": "longsword", "armor": "chain mail"},
    },
    {
        "key": "wizard", "name": "Wizard", "description": "A scholarly spellcaster.",
        "hit_die": 6, "primary_attribute_key": "int", "proficiencies": {"weapons": "simple"},
        "spellcasting": True, "starting_equipment": {"weapon": "quarterstaff", "gear": "spellbook"},
    },
    {
        "key": "rogue", "name": "Rogue", "description": "A stealthy trickster.",
        "hit_die": 8, "primary_attribute_key": "dex", "proficiencies": {"weapons": "simple, hand crossbow, rapier"},
        "spellcasting": False, "starting_equipment": {"weapon": "shortsword", "gear": "thieves' tools"},
    },
    {
        "key": "cleric", "name": "Cleric", "description": "A devoted channel of divine power.",
        "hit_die": 8, "primary_attribute_key": "wis", "proficiencies": {"armor": "light, medium, shields"},
        "spellcasting": True, "starting_equipment": {"weapon": "mace", "armor": "scale mail"},
    },
]
