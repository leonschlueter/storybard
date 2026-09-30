from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import ForeignKey, Integer, Interval, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class Clock(Base):
    """N-segment progress clock on a Thread. A thread can have multiple (racing clocks —
    "players stop the ritual" vs. "ritual completes" is more interesting than one doom
    clock). See spec.md.
    """

    __tablename__ = "clocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("threads.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    segments_total: Mapped[int] = mapped_column(Integer, default=4)
    segments_filled: Mapped[int] = mapped_column(Integer, default=0)

    # time_elapsed | player_action | linked_thread_complete — typed, not "the LLM decides
    # sometimes" (spec principle #1).
    tick_source: Mapped[str] = mapped_column(String(32), default="player_action")
    visibility: Mapped[str] = mapped_column(String(16), default="hidden")  # hidden | player_visible

    # Only meaningful for tick_source="time_elapsed" clocks: how much in-game time equals
    # one segment. World Sim Tick converts elapsed Campaign time into segments at this
    # clock's own rate (elapsed // real_time_per_segment), replacing the flat +1-per-call
    # placeholder from Phase 2B. See spec.md "Clock" / "What a tick actually is, now."
    real_time_per_segment: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)

    # No consequence_op field here (removed — see migration): it was defined and read by
    # _tick_clock but nothing ever set it, reachable only via direct DB manipulation. The
    # established pattern instead (see chain/ops.py's AbandonBeatOp) is a sibling WorldOp
    # in the same batch — only top-level discriminated-union ops get real grammar-
    # constrained-decoding benefit, a nested op-inside-a-JSON-column doesn't.
