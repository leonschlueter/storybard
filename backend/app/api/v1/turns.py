from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import structlog

from app.db.session import get_db
from app.schemas.api import TurnRequest, TurnResponse, RollSubmitRequest
from app.services.llm.ollama_client import OllamaClient
from app.services.llm.roles import LLMRoles
from app.services.pipeline.turn_pipeline import TurnPipeline

log = structlog.get_logger()
router = APIRouter()

def _pipeline():
    client = OllamaClient()
    llm = LLMRoles(client)
    return client, TurnPipeline(llm)

@router.post("/turns/{actor_id}", response_model=TurnResponse)
def run_turn(actor_id: str, req: TurnRequest, db: Session = Depends(get_db)):
    client, pipeline = _pipeline()
    try:
        result = pipeline.begin_turn(db=db, actor_id=actor_id, text=req.text)
        if result.get("status") != "ok":
            return TurnResponse(
                status="error",
                phase=result.get("phase","error"),
                campaign_id=result.get("campaign_id",""),
                actor_id=actor_id,
                mode=result.get("mode",""),
                campaign_time=result.get("campaign_time",""),
                narration=None,
                pending_roll=None,
                debug={"error": result},
            )
        return TurnResponse(**result)
    finally:
        client.close()

@router.post("/rolls/{pending_roll_id}", response_model=TurnResponse)
def submit_roll(pending_roll_id: str, req: RollSubmitRequest, db: Session = Depends(get_db)):
    client, pipeline = _pipeline()
    try:
        result = pipeline.resolve_roll(db=db, pending_roll_id=pending_roll_id, d20=req.d20)
        if result.get("status") != "ok":
            return TurnResponse(
                status="error",
                phase=result.get("phase","error"),
                campaign_id=result.get("campaign_id",""),
                actor_id=result.get("actor_id",""),
                mode=result.get("mode",""),
                campaign_time=result.get("campaign_time",""),
                narration=None,
                pending_roll=None,
                debug={"error": result},
            )
        return TurnResponse(**result)
    finally:
        client.close()
