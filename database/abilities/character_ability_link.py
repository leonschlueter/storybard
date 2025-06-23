from sqlalchemy import Column, Integer, String, Text, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from database.db_helper import Base

# abilities/character_ability_link.py
class CharacterAbilityLink(Base):
    __tablename__ = "character_abilities"

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id"))
    ability_id = Column(Integer, ForeignKey("combat_abilities.id"))
    times_used = Column(Integer, default=0)

    character = relationship("Character", backref="combat_abilities")
    ability = relationship("CombatAbility", backref="users")
