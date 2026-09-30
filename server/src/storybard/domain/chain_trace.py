from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TurnRun(Base):
    """One per player action. `id` doubles as the LangGraph checkpoint thread_id
    (LangGraph's own "thread" concept — a checkpoint session key — is unrelated to our
    domain's narrative `Thread`; never conflate the two)."""

    __tablename__ = "turn_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    action_text: Mapped[str] = mapped_column(String(4000))
    # running | paused | completed | abandoned — "abandoned" (api/turns.py's abandon
    # route) is the explicit, non-silent way out of a turn stuck mid-review (e.g. the
    # player typed a new action without resolving the pending step first) — without it,
    # create_turn's in-flight guard would permanently block the actor on a turn nobody
    # intends to finish. Never set implicitly; only a direct player action sets it.
    status: Mapped[str] = mapped_column(String(32), default="running")
    final_narration: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChainStep(Base):
    __tablename__ = "chain_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("turn_runs.id"), index=True
    )

    node_type: Mapped[str] = mapped_column(String(64))  # intent_parse | plausibility | mechanical_check | narrator
    sequence: Mapped[int] = mapped_column(Integer)

    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_output: Mapped[dict] = mapped_column(JSON, default=dict)
    final_output: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | approved | edited | retried

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
