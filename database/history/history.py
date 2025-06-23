# models/game_history.py
from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_helper import Base

class GameHistory(Base):
    __tablename__ = "game_history"

    id = Column(Integer, primary_key=True)
    player_input = Column(Text)
    narration = Column(Text)
    timestamp = Column(DateTime, default=datetime.now())

