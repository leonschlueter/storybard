# items/item.py
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database.db_helper import Base
from sqlalchemy import Enum as SqlEnum
from enum import Enum as PyEnum

class ItemType(PyEnum):
    WEAPON = "weapon"
    ARMOR = "armor"
    POTION = "potion"
    SCROLL = "scroll"
    MISC = "misc"

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    item_type = Column(SqlEnum(ItemType, name="item_type"), nullable=False)

    weight = Column(Float)
    value = Column(Integer)
    tags = Column(String)  # e.g., "magical,rare,cursed"

    player_id = Column(Integer, ForeignKey("players.id"))
    owner_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    equipped = Column(Boolean, default=False)

    owner = relationship("Character", backref="inventory")
    player = relationship("Player", back_populates="inventory")
