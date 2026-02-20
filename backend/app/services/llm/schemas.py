from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

from app.utils.enums import DifficultyBand, Phase, RollType


class IntentOut(BaseModel):
    primitive: Literal[
        "move",
        "speak",
        "interact",
        "inspect",
        "use_item",
        "cast_spell",
        "rest",
        "wait",
        "downtime_action",
        "attack",
        "unknown",
    ] = "unknown"
    target: Optional[str] = None
    requested_mode: Optional[Literal["explore", "downtime", "battle"]] = None
    notes: List[str] = Field(default_factory=list)


class CheckAdviceOut(BaseModel):
    phase: Phase = Phase.narrative
    roll_type: Optional[RollType] = None
    skill: Optional[str] = None

    dc: Optional[int] = None
    difficulty: Optional[DifficultyBand] = None
    dc_reason: Optional[str] = None

    time_passed_minutes: int = 0
    time_reason: Optional[str] = None

    mode_change_to: Optional[Literal["explore", "downtime", "battle"]] = None
    notes: List[str] = Field(default_factory=list)


class KnowledgeSelectionOut(BaseModel):
    world_nodes: List[str] = Field(default_factory=list)
    actors: List[str] = Field(default_factory=list)
    lore_pages: List[str] = Field(default_factory=list)
    context_blocks: List[str] = Field(default_factory=list)
    threads: List[str] = Field(default_factory=list)
    item_defs: List[str] = Field(default_factory=list)
    spell_defs: List[str] = Field(default_factory=list)
    why: List[str] = Field(default_factory=list)


OpType = Literal[
    "create_world_node",
    "create_actor",
    "move_actor",
    "create_lore_page",
    "create_context_block",
    "update_context_block",
    "create_story_thread",
    "update_story_thread",
    "create_item_def",
    "create_spell_def",
    "grant_item",
    "grant_spell",
    "create_actor_profile",
    "create_memory",
    "update_scene",
]


class Op(BaseModel):
    op: OpType
    data: Dict[str, Any]


class GMPlannerOut(BaseModel):
    """Director output that is meant to be fed into the narrator."""

    time_passed_minutes: int = 0
    time_reason: Optional[str] = None

    # Friends & Fables style "Thoughts" panel
    introspection: str
    pacing: str
    plan: str

    # small, declarative reminders for consistency
    world_facts: List[str] = Field(default_factory=list)
    scene_focus: List[str] = Field(default_factory=list)

    # Optional: ask the engine to retrieve lore (kept empty by default)
    retrieval_queries: List[str] = Field(default_factory=list)


class WorldUpdateOut(BaseModel):
    """Optional second pass that can safely create/update world entities."""

    ops: List[Op] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class NarratorOut(BaseModel):
    narration: str
    followups: List[Dict[str, Any]] = Field(default_factory=list)
    ui_hints: List[Dict[str, Any]] = Field(default_factory=list)


class MemoryOut(BaseModel):
    ops: List[Op] = Field(default_factory=list)


class ThreadAdvanceOut(BaseModel):
    ops: List[Op] = Field(default_factory=list)


class SeedWorldNode(BaseModel):
    name: str
    description: str
    x: float | None = None
    y: float | None = None
    tags: List[str] = Field(default_factory=list)


class SeedNPC(BaseModel):
    name: str
    bio: str
    start_location: str


class SeedLore(BaseModel):
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)


class SeedThread(BaseModel):
    title: str
    summary: str
    priority: float = 0.6
    initial_state: Dict[str, Any] = Field(default_factory=dict)


class SeedItem(BaseModel):
    name: str
    base_type: str = "generic"
    weight: float = 0.0
    rarity: str = "common"
    effect: Dict[str, Any] = Field(default_factory=dict)
    display_description: str | None = None
    visual_tags: List[str] = Field(default_factory=list)


class SeedSpell(BaseModel):
    name: str
    level: int = 0
    school: str = "universal"
    range: str = "self"
    duration: str = "instant"
    components: str = "V,S"
    effect: Dict[str, Any] = Field(default_factory=dict)
    display_description: str | None = None
    visual_tags: List[str] = Field(default_factory=list)


class CampaignSeedOut(BaseModel):
    campaign_summary: str
    world_nodes: List[SeedWorldNode]
    lore: List[SeedLore]
    npcs: List[SeedNPC]
    threads: List[SeedThread]
    starter_items: List[SeedItem] = Field(default_factory=list)
    starter_spells: List[SeedSpell] = Field(default_factory=list)
    start_location: str
    calendar_name: str = "Gregorian"
    start_date_iso: str  # YYYY-MM-DD

# --- Location detail writer ---
class LocationDetailOut(BaseModel):
    name: str
    short_description: str
    long_description: str
    tags: List[str] = Field(default_factory=list)
    x: float | None = None
    y: float | None = None
    nearby: List[Dict[str, Any]] = Field(default_factory=list)  # [{"name":..., "minutes":..., "reason":...}]

# --- NPC sheet writer (full sheet every time) ---
class NPCSheetOut(BaseModel):
    name: str
    bio: str
    pronouns: str | None = None
    species: str | None = None
    age: int | None = None
    occupation: str | None = None
    alignment: str | None = None
    faction: str | None = None

    appearance: str
    personality: str
    mannerisms: str
    backstory: str
    goals: List[str] = Field(default_factory=list)

    # D&D-ish combat/stat block (lightweight)
    level: int = 1
    class_name: str | None = None
    max_hp: int = 10
    armor_class: int = 10
    speed: int = 30
    abilities: Dict[str, int] = Field(default_factory=lambda: {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})
    skills: List[str] = Field(default_factory=list)

    # Relationships / memories seeds (stored as Memory rows)
    memories: List[Dict[str, Any]] = Field(default_factory=list)  # [{"title":..., "text":..., "importance":1..5, "subject_name":optional}]
