from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class WorldNode(Base):
    """A location, at any scale — a world, a country, a village, an inn, a room. Hierarchy
    is uncapped (unlike Thread's depth cap): locations don't have Thread's fractal-
    explosion risk, so there's no need to bound nesting. See spec.md "Entity creation" /
    "World" for the full design, including the lowest-common-ancestor distance calc in
    services/geography.py that this hierarchy exists to support.
    """

    __tablename__ = "world_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_long: Mapped[str | None] = mapped_column(Text, nullable=True)

    danger_level: Mapped[int] = mapped_column(Integer, default=1)

    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("world_nodes.id"), nullable=True, index=True
    )
    depth: Mapped[int] = mapped_column(Integer, default=0)  # 0 for a root node, 1+ per nesting level
    # Free text, not a hardcoded enum — "region"/"settlement"/"room", or a thematic
    # reskin, is a data choice, not a schema change. Matches AttributeDefinition's
    # display_name precedent. Optional: not every node needs one.
    scale: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Local to the parent's coordinate space, not global — a child node's (x, y) only means
    # something relative to its own parent. See services/geography.py for how cross-branch
    # distance is computed despite this (lowest-common-ancestor projection).
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
