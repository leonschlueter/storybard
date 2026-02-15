import uuid
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), default="New Campaign")
    user_id: Mapped[str] = mapped_column(String(200), default="local-dev")

    seed: Mapped[int] = mapped_column(default=0)
    world_time: Mapped[int] = mapped_column(default=0)  # ticks or minutes, your choice
    tone_vector: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)
