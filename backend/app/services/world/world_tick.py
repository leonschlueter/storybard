from __future__ import annotations

from sqlalchemy.orm import Session

def world_tick(db: Session, campaign_id: str, minutes_passed: int) -> None:
    # Placeholder for future world simulation.
    # In this dev build, we keep it deterministic and minimal.
    # You can later add an LLM call to propose world events and apply ops.
    return
