from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from app.utils.enums import DifficultyBand, Phase, RollType

# --- Intent parsing ---
class IntentOut(BaseModel):
    primitive: Literal[
        "move","speak","interact","inspect","use_item","cast_spell","rest","wait",
        "downtime_action","attack","unknown"
    ] = "unknown"
    target: Optional[str] = None
    requested_mode: Optional[Literal["explore","downtime","battle"]] = None
    notes: List[str] = Field(default_factory=list)

# --- Check advice (LLM proposes DC + reason; engine enforces) ---
class CheckAdviceOut(BaseModel):
    phase: Phase = Phase.narrative
    roll_type: Optional[RollType] = None
    skill: Optional[str] = None

    dc: Optional[int] = None
    difficulty: Optional[DifficultyBand] = None
    dc_reason: Optional[str] = None

    time_passed_minutes: int = 0
    time_reason: Optional[str] = None

    # For future: allow mode change suggestions
    mode_change_to: Optional[Literal["explore","downtime","battle"]] = None
    notes: List[str] = Field(default_factory=list)

# --- Knowledge selection (IDs only) ---
class KnowledgeSelectionOut(BaseModel):
    world_nodes: List[str] = Field(default_factory=list)
    actors: List[str] = Field(default_factory=list)
    lore_pages: List[str] = Field(default_factory=list)
    context_blocks: List[str] = Field(default_factory=list)
    threads: List[str] = Field(default_factory=list)
    item_defs: List[str] = Field(default_factory=list)
    spell_defs: List[str] = Field(default_factory=list)
    why: List[str] = Field(default_factory=list)

# --- Ops ---
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
]

class Op(BaseModel):
    op: OpType
    data: Dict[str, Any]

# --- GM planner output ---
class GMPlannerOut(BaseModel):
    time_passed_minutes: int = 0
    time_reason: Optional[str] = None
    ops: List[Op] = Field(default_factory=list)
    gm_notes: List[str] = Field(default_factory=list)

# --- Narrator output ---
class NarratorOut(BaseModel):
    narration: str
    followups: List[Dict[str, Any]] = Field(default_factory=list)
    ui_hints: List[Dict[str, Any]] = Field(default_factory=list)

# --- Memory regression output ---
class MemoryOut(BaseModel):
    ops: List[Op] = Field(default_factory=list)

# --- Thread advancer ---
class ThreadAdvanceOut(BaseModel):
    ops: List[Op] = Field(default_factory=list)

# --- Campaign seeder output ---
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
