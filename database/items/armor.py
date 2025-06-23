from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship
from database.db_helper import Base

# items/armor.py
class Armor(Base):
    __tablename__ = "armors"

    id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    armor_class = Column(Integer)
    slot = Column(String)  # head, chest, legs
    armor_type = Column(String)  # light, medium, heavy
    penalties = Column(Text)  # movement, stealth

    item = relationship("Item", backref="armor_data")
