# /models/locations/region.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from database.db_helper import Base

class RegionData(Base):
    __tablename__ = "region_data"

    id = Column(Integer, ForeignKey("locations.id"), primary_key=True)

    climate = Column(String)
    terrain = Column(String)
    danger_level = Column(Integer)  # 0–10
    resource_abundance = Column(Integer)  # 0–10
    dominant_species = Column(String)

    summary = Column(Text)
    location = relationship("Location", backref="region_data")
