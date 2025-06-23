# models/hook.py
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_helper import Base

class Hook(Base):
    __tablename__ = "hooks"

    id = Column(Integer, primary_key=True)
    arc_id = Column(Integer, ForeignKey("narrative_arcs.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    description = Column(Text, nullable=False)
    tags = Column(String)
    discovered_by_players = Column(Boolean, default=False)
    discovered_at = Column(DateTime, nullable=True)

    arc = relationship("NarrativeArc", back_populates="hooks")
    location = relationship("Location", back_populates="hooks")
