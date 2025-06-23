# schemas/gm_intent.py
from typing import Optional, Literal
from pydantic import BaseModel


class GMIntent(BaseModel):
    id: Optional[int] = None
    intention: str
    tone: str  # e.g. "tense", "hopeful", "mysterious"
    pacing_goal: Optional[str]
    narrative_risk: Optional[int] = 50
    impact_estimate: Optional[Literal["minor", "moderate", "high"]]
    reasoning: Optional[str]

    target_type: Optional[Literal["scene", "arc", "thread"]] = None
    target_id: Optional[int] = None

    is_active: bool = False
    is_consumed: bool = False

    priority: Optional[int] = 50
    tags: Optional[str] = None

    class Config:
        orm_mode = True
