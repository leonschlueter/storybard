from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class ThreadBeat(Base):
    """A staged, planned step within a Thread's progression — the "x, y, z planned but
    shiftable, with consequences" concept a Thread's title/summary/Clock alone couldn't
    express. Real table off Thread, not a JSON field, matching Clock's existing precedent
    (thread_id as a real FK, not campaign_id) — beats need individually addressable state
    transitions via ops (fire/abandon), same reasoning Clock already established.

    Deliberately no consequence_op field (unlike Clock.consequence_op, which turned out to
    be dead code — defined, read, but never actually settable by any op): a free-form dict
    field gets no grammar-constrained-decoding benefit, the exact weak-typing trap this
    codebase's StrictOut discipline exists to avoid. Abandoning a beat's real consequence,
    when one is warranted, is a sibling op in the same World Update batch instead — see
    chain/prompts.py::world_update_prompt and chain/ops.py::AbandonBeatOp.
    """

    __tablename__ = "thread_beats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("threads.id"), index=True)

    order_index: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | fired | abandoned

    # Where this beat is "due" — null means it applies regardless of location (see
    # services/context_assembly.py::build_scene).
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
