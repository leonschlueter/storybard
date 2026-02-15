import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, TEXT
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id"),
        index=True,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("actors.id"),
        index=True,
    )

    action_text: Mapped[str] = mapped_column(TEXT)

    parsed_intent: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )

    result_data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )

    narration_text: Mapped[str | None] = mapped_column(
        TEXT,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
