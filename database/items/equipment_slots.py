# items/item.py
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database.db_helper import Base

class EquipmentSlot(Base):
    __tablename__ = "equipment_slots"

    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    slot_type = Column(String)  # "head", "main_hand", "off_hand", etc.
