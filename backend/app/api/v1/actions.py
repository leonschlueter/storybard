from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.action_engine import action_engine

router = APIRouter()


@router.post("/")
def perform_action(actor_id: str, text: str, db: Session = Depends(get_db)):
    return action_engine.handle(actor_id=actor_id, text=text, db=db)
