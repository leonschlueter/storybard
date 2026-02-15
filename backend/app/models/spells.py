import uuid
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db.base import Base


class SpellDefinition(Base):
    __tablename__ = "spell_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(200), index=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    school: Mapped[str] = mapped_column(String(50), default="")

    casting_time: Mapped[str] = mapped_column(String(50), default="")
    spell_range: Mapped[str] = mapped_column(String(50), default="")
    duration: Mapped[str] = mapped_column(String(50), default="")
    components: Mapped[str] = mapped_column(String(50), default="")

    requires_concentration: Mapped[bool] = mapped_column(Boolean, default=False)
    effect_data: Mapped[dict] = mapped_column(JSONB, default=dict)


class ActorSpell(Base):
    __tablename__ = "actor_spells"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), primary_key=True)
    spell_definition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spell_definitions.id"), primary_key=True)

    prepared: Mapped[bool] = mapped_column(Boolean, default=False)


class ActorSpellSlot(Base):
    __tablename__ = "actor_spell_slots"

    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), primary_key=True)
    spell_level: Mapped[int] = mapped_column(Integer, primary_key=True)

    total: Mapped[int] = mapped_column(Integer, default=0)
    remaining: Mapped[int] = mapped_column(Integer, default=0)
