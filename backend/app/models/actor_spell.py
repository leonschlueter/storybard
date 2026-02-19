from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, ForeignKey
from app.db.base import Base

class ActorSpell(Base):
    __tablename__ = "actor_spells"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String, ForeignKey("actors.id"), index=True)
    spell_def_id: Mapped[str] = mapped_column(String, ForeignKey("spell_defs.id"), index=True)
    prepared: Mapped[bool] = mapped_column(Boolean, default=True)
