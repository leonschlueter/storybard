from typing import Optional
from pydantic import BaseModel


class StoryState(BaseModel):
    suspense_level: int  # 0–100
    pacing: str  # e.g., "slow", "rising", "high", "fallout"
    emotional_tone: str  # e.g., "grim", "light", "mysterious"
    story_beat: Optional[str] = None  # exposition, escalation, climax, etc.
