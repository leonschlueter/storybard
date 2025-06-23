# abilities/combat_ability.py
from sqlalchemy import Column, Integer, String, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from database.db_helper import Base

class AbilityType(Enum):
    MELEE = "melee"
    RANGED = "ranged"
    DEFENSIVE = "defensive"
    UTILITY = "utility"

class CombatAbility(Base):
    __tablename__ = "combat_abilities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    ability_type = Column(Enum(AbilityType))
    
    level_required = Column(Integer, default=1)
    uses_per_day = Column(Integer, nullable=True)  # optional
    cooldown_turns = Column(Integer, nullable=True)
    
    cost = Column(String)  # e.g., "1 action", "bonus action"
    effect_summary = Column(Text)

    tags = Column(String)  # "aoe,knockdown,bleed"
