from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database.db_helper import Base

class Spell(Base):
    __tablename__ = "spells"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)
    level = Column(Integer)
    school = Column(String)
    casting_time = Column(String)
    range = Column(String)
    components = Column(String)
    material_components = Column(String)
    duration = Column(String)
    concentration = Column(Boolean)
    ritual = Column(Boolean)
    damage_type = Column(String)
    damage_at_slot_level = Column(String)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
