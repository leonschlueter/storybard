# models/gm_intent.py
from sqlalchemy import Column, Integer, String, Boolean, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from database.db_helper import Base

class GMIntent(Base):
    __tablename__ = "gm_intents"

    id = Column(Integer, primary_key=True)
    intention = Column(Text, nullable=False)
    tone = Column(String, default="neutral")
    pacing_goal = Column(String)
    narrative_risk = Column(Integer, default=50)
    impact_estimate = Column(String)  # "minor", "moderate", "high"
    reasoning = Column(Text)

    # Targeting
    target_type = Column(Enum("scene", "arc", "thread", name="intent_target_type"), nullable=True)
    target_id = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=False)
    is_consumed = Column(Boolean, default=False)

    # Optional metadata
    priority = Column(Integer, default=50)
    tags = Column(String)  # e.g. "mystery,politics"
