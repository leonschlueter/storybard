import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), index=True)

    type: Mapped[str] = mapped_column(String(20), index=True)  # player/npc
    name: Mapped[str] = mapped_column(String(200))

    race: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alignment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    background: Mapped[str | None] = mapped_column(String(100), nullable=True)

    level_total: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    hp_current: Mapped[int] = mapped_column(Integer, default=10)
    hp_max: Mapped[int] = mapped_column(Integer, default=10)

    current_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("world_nodes.id"), nullable=True, index=True
    )

    flags: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)


class ActorAbilityScores(Base):
    __tablename__ = "actor_ability_scores"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), primary_key=True)

    strength: Mapped[int] = mapped_column(Integer, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, default=10)
    constitution: Mapped[int] = mapped_column(Integer, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, default=10)
    charisma: Mapped[int] = mapped_column(Integer, default=10)


class ActorClass(Base):
    __tablename__ = "actor_classes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), index=True)

    class_name: Mapped[str] = mapped_column(String(100))
    subclass_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)


class ActorProficiency(Base):
    __tablename__ = "actor_proficiencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), index=True)

    proficiency_type: Mapped[str] = mapped_column(String(30), index=True)  # skill/save/tool/weapon/armor
    name: Mapped[str] = mapped_column(String(100), index=True)
    expertise: Mapped[bool] = mapped_column(Boolean, default=False)


class ActorResource(Base):
    __tablename__ = "actor_resources"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), primary_key=True)

    gold: Mapped[int] = mapped_column(Integer, default=0)
    exhaustion_level: Mapped[int] = mapped_column(Integer, default=0)
    inspiration: Mapped[bool] = mapped_column(Boolean, default=False)

    custom: Mapped[dict] = mapped_column(JSONB, default=dict)  # ki points, sorcery points later, etc.


class ActorFeature(Base):
    __tablename__ = "actor_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), index=True)

    feature_name: Mapped[str] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(String(50), default="class")  # class/race/background/etc
    level_acquired: Mapped[int] = mapped_column(Integer, default=1)

    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
