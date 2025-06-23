from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database.db_helper import Base

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True, index=True)
    character_name = Column(String)
    level = Column(Integer)
    xp = Column(Integer)
    race = Column(String)
    gold = Column(Integer)
    current_hp = Column(Integer)
    max_hp = Column(Integer)

    # Stats
    STR = Column(Integer)
    DEX = Column(Integer)
    CON = Column(Integer)
    INT = Column(Integer)
    WIS = Column(Integer)
    CHA = Column(Integer)

    inventory = relationship("Item", back_populates="player")
        