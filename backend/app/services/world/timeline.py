from __future__ import annotations
from datetime import datetime, timedelta

def advance_time(current: datetime, minutes: int) -> datetime:
    minutes = max(0, int(minutes))
    return current + timedelta(minutes=minutes)
