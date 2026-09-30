from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class PlantedReveal(Base):
    """A GM-only hidden connection seeded at campaign start, meant to surface later as a
    twist — never fed to the player directly. Generated once by seed_narrative_prompt
    (chain/prompts.py), stored here, surfaced only in a GM-facing view (never in any
    player-facing prompt or endpoint). Scoped to storage + display for now, not yet wired
    into active narration decision-making — a natural first consumer once a Twist node
    exists. See the "All 20 Features" plan, feature #10.
    """

    __tablename__ = "planted_reveals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    secret_text: Mapped[str] = mapped_column(Text)
    connects_entity_ids: Mapped[list] = mapped_column(JSON, default=list)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False)
