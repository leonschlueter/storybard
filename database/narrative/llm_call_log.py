# threads/llm_call_log.py
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Boolean, String
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db_helper import Base

class LLMCallLog(Base):
    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True)

    prompt_text = Column(Text)
    response_text = Column(Text)
    model_used = Column(String)
    role = Column(String)  # "narration", "reaction", "summary"
    context_data = Column(Text)  # What info was included in the prompt
    tokens_used = Column(Integer)
    success = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.now())