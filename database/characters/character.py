# characters/character.py
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey
from database.db_helper import Base

class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    character_type = Column(String)  # "player", "npc"
    race = Column(String)
    class_name = Column(String)
    level = Column(Integer, default=1)

    health = Column(Integer)
    mana = Column(Integer)
    strength = Column(Integer)
    dexterity = Column(Integer)
    intelligence = Column(Integer)
    charisma = Column(Integer)

    background = Column(Text)
    is_alive = Column(Boolean, default=True)

    location_id = Column(Integer, ForeignKey("locations.id"))
    # Backref: location.characters

    def is_player(self):
        return self.character_type == "player"
