from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from database.db_helper import Base

# locations/world_data.py
class WorldData(Base):
    __tablename__ = "world_data"

    id = Column(Integer, ForeignKey("locations.id"), primary_key=True)
    
    age_years = Column(Integer)
    population = Column(Integer)
    magic_level = Column(Integer)  # 0–10
    tech_level = Column(Integer)   # 0–10
    known_planes = Column(Integer)

    summary = Column(Text)  # short LLM-ready overview
    location = relationship("Location", backref="world_data")
