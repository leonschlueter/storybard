# narrative/scene_link.py
from sqlalchemy import Column, Integer, ForeignKey, String
from database.db_helper import Base

class SceneLink(Base):
    __tablename__ = "scene_links"

    id = Column(Integer, primary_key=True)
    from_scene_id = Column(Integer, ForeignKey("narrative_scenes.id"))
    to_scene_id = Column(Integer, ForeignKey("narrative_scenes.id"))
    condition = Column(String)  # e.g., "if players betray NPC"
    note = Column(String)
