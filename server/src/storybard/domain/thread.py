from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base

# Maximum depth *value* a Thread can have. A major thread is depth 0; its direct minor
# children are depth 1; that's it for this phase — no minor-of-minor nesting yet ("2 levels"
# per spec.md means major + one minor tier, not three levels of depth values). A create op
# is rejected when `parent.depth + 1 > MAX_THREAD_DEPTH`, i.e. once the parent is already at
# the max, not one level before it — see the off-by-one this comment exists to prevent
# reintroducing, caught by tests/test_ops.py::TestCreateMinorThread::test_depth_cap_rejects.
MAX_THREAD_DEPTH = 1


class Thread(Base):
    """The single unit of narrative momentum — quest threads, NPC agendas, and faction
    goals are all just Threads, owned by different things. See spec.md "Narrative
    momentum: Thread, Clock, Hook" for the full design and the reasoning behind tiers.
    """

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | resolved | failed

    tier: Mapped[str] = mapped_column(String(16), default="minor")  # major | minor
    depth: Mapped[int] = mapped_column(Integer, default=0)  # 0 for major/top-level, 1+ for nested minors

    parent_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=True, index=True
    )
    relation: Mapped[str | None] = mapped_column(String(32), nullable=True)  # prerequisite | alternative | optional_aid

    owner_type: Mapped[str] = mapped_column(String(16), default="campaign")  # campaign | actor | faction
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # LLM/GM-settable, higher = more important. Restored in Phase 3A after being dropped in
    # the 2A redesign — context assembly needs this to decide what to surface first as the
    # number of active threads grows. Not currently gated/derived by anything in code.
    priority: Mapped[int] = mapped_column(Integer, default=0)
