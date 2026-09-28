from __future__ import annotations

import uuid

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class Faction(Base):
    """First-class object: goals, resources, reputation. Pursues its own agenda through
    the same Thread/Clock system as everything else — a faction's "war preparations" is
    just a Thread with owner_type="faction". See spec.md.
    """

    __tablename__ = "factions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals: Mapped[dict] = mapped_column(JSON, default=dict)
    reputation_baseline: Mapped[int] = mapped_column(Integer, default=0)
