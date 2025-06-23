from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship
from database.db_helper import Base


# items/weapon.py
class Weapon(Base):
    __tablename__ = "weapons"

    id = Column(Integer, ForeignKey("items.id"), primary_key=True)
    damage_die = Column(String)  # e.g., "1d8"
    weapon_type = Column(String)  # melee, ranged
    damage_type = Column(String)  # slashing, piercing
    range_meters = Column(Integer)

    item = relationship("Item", backref="weapon_data")