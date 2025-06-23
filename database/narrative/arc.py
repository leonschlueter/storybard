# narrative/arc.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_helper import Base

class NarrativeArc(Base):
    __tablename__ = "narrative_arcs"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    theme = Column(String)
    summary = Column(Text)
    player_visibility = Column(String, default="public")  # public, hidden, rumor
    progress_score = Column(Integer, default=0)
    importance = Column(Integer, default=50)
    tags = Column(String)

    hooks = relationship("Hook", back_populates="arc")
    created_at = Column(DateTime, default=datetime.now())

