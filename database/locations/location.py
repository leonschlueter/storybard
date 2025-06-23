# locations/location.py
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database.db_helper import Base

class LocationType(PyEnum):
    WORLD = "world"
    KINGDOM = "kingdom"
    REGION = "region"
    CITY = "city"
    BUILDING = "building"
    ROOM = "room"
    OTHER = "other"

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    location_type = Column(Enum(LocationType), nullable=False)

    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    parent = relationship("Location", remote_side=[id], backref="sub_locations")

    tags = Column(String)  # e.g., "foggy,haunted,trade-hub"
    hooks = relationship("Hook", back_populates="location")

    def full_path(self):
        """Returns full hierarchical path like 'World > Kingdom > City'"""
        current = self
        path = []
        while current:
            path.append(current.name)
            current = current.parent
        return " > ".join(reversed(path))
