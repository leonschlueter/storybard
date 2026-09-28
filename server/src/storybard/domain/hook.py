from __future__ import annotations

import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from storybard.core.db import Base


class Hook(Base):
    """A proposed-but-not-committed narrative development. The auto-accept vs.
    requires-approval gate is *structural*, not an LLM-self-judged severity score:
    `touches_entity_id` set means this recontextualizes something already established
    (always needs approval); null means it only creates new canon (safe to auto-accept).
    See spec.md "Hooks" and the workshop discussion on why severity-scoring was rejected.
    """

    __tablename__ = "hooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    origin: Mapped[str] = mapped_column(Text)  # what triggered this proposal
    proposed_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="proposed")  # proposed | accepted | rejected

    touches_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
