from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import structlog

from app.db.session import get_db
from app.schemas.api import SeedRequest, SeedResponse
from app.services.llm.ollama_client import OllamaClient
from app.services.llm.roles import LLMRoles
from app.services.world.campaign_seeder import seed_campaign
from app.models.scene import Scene
from sqlalchemy import select

log = structlog.get_logger()
router = APIRouter()

@router.post("/seed", response_model=SeedResponse)
def seed(req: SeedRequest, db: Session = Depends(get_db)):
    client = OllamaClient()
    llm = LLMRoles(client)
    try:
        camp, player, node = seed_campaign(
            db,
            llm,
            name=req.name,
            narration_style=req.narration_style,
            genre=req.genre,
            themes=req.themes,
            magic_level=req.magic_level,
            constraints=req.constraints,
        )
        scene = db.execute(
            select(Scene).where(Scene.campaign_id == camp.id, Scene.is_current == True)  # noqa: E712
        ).scalar_one_or_none()
        db.commit()
        return SeedResponse(
            campaign_id=camp.id,
            player_actor_id=player.id,
            start_node_id=node.id,
            scene_id=(scene.id if scene else None),
        )
    finally:
        client.close()
