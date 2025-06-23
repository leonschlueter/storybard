from typing import List, Optional, Literal
from pydantic import BaseModel
from schemas.gm_intent import GMIntent


class SceneUpdate(BaseModel):
    action: Literal["create", "update"]
    id: Optional[int] = None
    title: str
    setup: str
    arc_id: Optional[int]
    location_id: Optional[int]
    tension_level: Optional[int] = 50
    is_turning_point: Optional[bool] = False
    is_resolved: Optional[bool] = False


class SceneLinkUpdate(BaseModel):
    action: Literal["create"]
    from_scene_id: int
    to_scene_id: int
    condition: Optional[str] = None
    note: Optional[str] = None


class ArcUpdate(BaseModel):
    action: Literal["create", "update"]
    id: Optional[int] = None
    title: str
    theme: Optional[str] = None
    summary: Optional[str] = None
    importance: Optional[int] = 50
    tags: Optional[str] = None


class NarrativeUpdate(BaseModel):
    scenes: Optional[List[SceneUpdate]] = []
    scene_links: Optional[List[SceneLinkUpdate]] = []
    arcs: Optional[List[ArcUpdate]] = []
    gm_intents: Optional[List[GMIntent]] = []
