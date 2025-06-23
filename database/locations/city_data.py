from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from database.db_helper import Base

class CityData(Base):
    __tablename__ = "city_data"

    id = Column(Integer, ForeignKey("locations.id"), primary_key=True)

    population = Column(Integer)
    economy_type = Column(String)  # trade, mining, arcane
    crime_index = Column(Integer)  # 0–100
    law_strength = Column(Integer)  # 0–100
    founding_year = Column(Integer)

    mayor_name = Column(String)
    district_count = Column(Integer)

    summary = Column(Text)
    location = relationship("Location", backref="city_data")

