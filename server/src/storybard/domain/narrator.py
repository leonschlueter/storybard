from __future__ import annotations

import uuid

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class NarratorProfile(Base):
    """Style + verbosity only for Phase 0. Full persona (humor, agency stance, system-talk
    transparency, narrative volatility — see spec.md Campaign Seed Screen Step 2) is Phase 3.
    """

    __tablename__ = "narrator_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    name: Mapped[str] = mapped_column(String(120), default="Default Narrator")
    style_description: Mapped[str] = mapped_column(Text, default="")
    verbosity_target_words: Mapped[float] = mapped_column(Float, default=150.0)
