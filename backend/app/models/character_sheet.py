from __future__ import annotations
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, ForeignKey
from app.db.base import Base

class CharacterSheet(Base):
    __tablename__ = "character_sheets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(String, ForeignKey("actors.id"), unique=True, index=True)

    level: Mapped[int] = mapped_column(Integer, default=1)
    class_name: Mapped[str] = mapped_column(String(64), default="Fighter")
    race: Mapped[str] = mapped_column(String(64), default="Human")
    background: Mapped[str] = mapped_column(String(128), default="Soldier")

    ability_scores: Mapped[dict] = mapped_column(JSON, default=dict)  # STR/DEX/CON/INT/WIS/CHA
    proficiencies: Mapped[dict] = mapped_column(JSON, default=dict)   # skills, saves, weapons, armor
    max_hp: Mapped[int] = mapped_column(Integer, default=12)
    current_hp: Mapped[int] = mapped_column(Integer, default=12)
    armor_class: Mapped[int] = mapped_column(Integer, default=10)
    speed: Mapped[int] = mapped_column(Integer, default=30)

    gold: Mapped[int] = mapped_column(Integer, default=10)

    spell_slots: Mapped[dict] = mapped_column(JSON, default=dict)     # per level, later
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
