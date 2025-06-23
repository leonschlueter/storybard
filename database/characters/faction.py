from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from database.db_helper import Base

class Faction(Base):
    __tablename__ = "factions"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)
    alignment = Column(String)
    influence = Column(Integer)
    headquarters_id = Column(Integer, ForeignKey("locations.id"))
