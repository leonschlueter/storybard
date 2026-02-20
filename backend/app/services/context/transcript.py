from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event


def build_transcript(db: Session, *, campaign_id: str, max_chars: int | None = None) -> str:
    """Build a narrator<->player transcript limited by max characters."""
    max_chars = int(max_chars or settings.NARRATOR_TRANSCRIPT_MAX_CHARS)

    # Pull a reasonable number of recent events and then trim from the end.
    evs = (
        db.execute(
            select(Event)
            .where(Event.campaign_id == campaign_id)
            .order_by(Event.created_at.desc())
            .limit(40)
        )
        .scalars()
        .all()
    )
    evs = list(reversed(evs))

    lines: list[str] = []
    for e in evs:
        if e.action_text:
            lines.append(f"**Player:** {e.action_text}")
        if e.narration:
            lines.append(f"**Narrator:** {e.narration}")
        lines.append("")

    full = "\n".join(lines).strip()
    if len(full) <= max_chars:
        return full
    return full[-max_chars:]
