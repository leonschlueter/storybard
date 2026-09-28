from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    name: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="npc")  # player | npc | companion
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A persistent one-line "what does this character want right now" note — set at
    # creation, updatable later via UpdateActorOp (chain/ops.py) so an NPC's motive stays
    # consistent across many turns instead of being reinvented from a static bio each time.
    current_goal: Mapped[str | None] = mapped_column(Text, nullable=True)

    current_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("world_nodes.id"), nullable=True
    )


class ActorProfile(Base):
    __tablename__ = "actor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), unique=True, index=True
    )

    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    backstory: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class CharacterSheet(Base):
    __tablename__ = "character_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), unique=True, index=True
    )

    level: Mapped[int] = mapped_column(Integer, default=1)
    ancestry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    character_class: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # dict[AttributeDefinition.key, score] — see domain/ruleset.py. Never hardcoded columns.
    ability_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    proficiencies: Mapped[dict] = mapped_column(JSON, default=dict)

    max_hp: Mapped[int] = mapped_column(Integer, default=10)
    current_hp: Mapped[int] = mapped_column(Integer, default=10)
    armor_class: Mapped[int] = mapped_column(Integer, default=10)
    speed: Mapped[int] = mapped_column(Integer, default=30)
