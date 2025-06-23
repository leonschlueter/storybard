from typing import List, Optional, Literal
from pydantic import BaseModel


class CharacterUpdate(BaseModel):
    action: Literal["create", "update"]
    id: Optional[int] = None
    name: str
    summary: Optional[str] = None
    role: Optional[str] = None
    tags: Optional[str] = None


class ItemUpdate(BaseModel):
    action: Literal["create", "update"]
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    item_type: Optional[str] = None
    tags: Optional[str] = None


class LocationUpdate(BaseModel):
    action: Literal["create", "update"]
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    tags: Optional[str] = None


class HookUpdate(BaseModel):
    action: Literal["create", "update"]
    id: Optional[int] = None
    description: str
    arc_id: Optional[int]
    location_id: Optional[int]
    discovered_by_players: Optional[bool] = False
    tags: Optional[str] = None


class WorldEntityUpdate(BaseModel):
    characters: Optional[List[CharacterUpdate]] = []
    items: Optional[List[ItemUpdate]] = []
    locations: Optional[List[LocationUpdate]] = []
    hooks: Optional[List[HookUpdate]] = []
