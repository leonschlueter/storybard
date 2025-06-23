# narrative/scene.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_helper import Base

class NarrativeScene(Base):
    __tablename__ = "narrative_scenes"

    id = Column(Integer, primary_key=True)
    arc_id = Column(Integer, ForeignKey("narrative_arcs.id"))
    title = Column(String, nullable=False)
    setup = Column(Text)
    resolution = Column(Text)
    gm_notes = Column(Text)

    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    visible_to_players = Column(Boolean, default=True)
    is_turning_point = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    tension_level = Column(Integer, default=0)  # 0–100 for scene drama level

    created_at = Column(DateTime, default=datetime.now())

    arc = relationship("NarrativeArc", backref="scenes")
    location = relationship("Location")

