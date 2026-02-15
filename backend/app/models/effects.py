import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db.base import Base


class ActiveEffect(Base):
    __tablename__ = "active_effects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    target_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), index=True)
    source_actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True)

    effect_type: Mapped[str] = mapped_column(String(50), index=True)  # condition/buff/debuff
    name: Mapped[str] = mapped_column(String(200), index=True)

    magnitude: Mapped[int] = mapped_column(Integer, default=0)
    duration_rounds: Mapped[int] = mapped_column(Integer, default=0)

    concentration: Mapped[bool] = mapped_column(Boolean, default=False)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)
