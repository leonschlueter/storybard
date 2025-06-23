from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from database.db_helper import Base

# locations/kingdom_data.py
class KingdomData(Base):
    __tablename__ = "kingdom_data"

    id = Column(Integer, ForeignKey("locations.id"), primary_key=True)

    population = Column(Integer)
    military_strength = Column(Integer)  # 0–100
    economy_rating = Column(Integer)  # 0–10
    political_stability = Column(Integer)  # 0–100
    magic_policy = Column(String)  # "restricted", "regulated", "banned", "open"

    ruler_name = Column(String)
    capital_city = Column(String)

    summary = Column(Text)
    location = relationship("Location", backref="kingdom_data")
