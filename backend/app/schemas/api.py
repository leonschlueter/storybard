from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional

class SeedRequest(BaseModel):
    name: str = "Test Campaign"
    narration_style: str = "basic_fantasy"
    genre: str = "fantasy"
    themes: list[str] = Field(default_factory=lambda: ["mystery", "frontier", "ancient ruins"])
    magic_level: str = "medium"
    constraints: list[str] = Field(default_factory=lambda: ["keep it medium-sized", "include 3 story threads"])

class SeedResponse(BaseModel):
    campaign_id: str
    player_actor_id: str
    start_node_id: str

class TurnRequest(BaseModel):
    text: str

class TurnResponse(BaseModel):
    status: str
    phase: str
    campaign_id: str
    actor_id: str
    mode: str
    campaign_time: str

    narration: str | None = None
    pending_roll: dict[str, Any] | None = None
    debug: dict[str, Any] = Field(default_factory=dict)

class RollSubmitRequest(BaseModel):
    d20: int = Field(ge=1, le=20)

class ContextBlockUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    full_text: str | None = None
    structured: dict[str, Any] | None = None
    priority: float | None = None
    ttl_turns: int | None = None
    is_active: bool | None = None

class CharacterCreateRequest(BaseModel):
    prompt: str
