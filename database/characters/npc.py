from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database.db_helper import Base

class NPC(Base):
    __tablename__ = "npcs"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(Text)
    location_id = Column(Integer, ForeignKey("locations.id"))
    disposition = Column(Integer, default=0)
    tags = Column(String)
    is_important = Column(Boolean, default=False)
