from __future__ import annotations
from enum import Enum

class CampaignMode(str, Enum):
    explore = "explore"
    downtime = "downtime"
    battle = "battle"

class ActorKind(str, Enum):
    player = "player"
    npc = "npc"

class RollType(str, Enum):
    skill_check = "skill_check"
    initiative = "initiative"

class Phase(str, Enum):
    narrative = "narrative"
    skill_check_required = "skill_check_required"
    initiative_required = "initiative_required"
    mode_change = "mode_change"
    invalid = "invalid"

class DifficultyBand(str, Enum):
    trivial = "trivial"
    easy = "easy"
    medium = "medium"
    hard = "hard"
    very_hard = "very_hard"
