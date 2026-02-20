from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.actor import Actor
from app.models.actor_profile import ActorProfile

router = APIRouter()


class ActorProfileUpsertIn(BaseModel):
    pronouns: str | None = None
    voice: str | None = None
    faction: str | None = None
    appearance: str | None = None
    personality: str | None = None
    mannerisms: str | None = None
    backstory: str | None = None
    goals: str | None = None
    secrets: str | None = None
    age: str | None = None
    species: str | None = None
    occupation: str | None = None
    alignment: str | None = None
    extra: dict | None = None


@router.get("/profiles/{actor_id}")
def get_profile(actor_id: str, db: Session = Depends(get_db)):
    a = db.execute(select(Actor).where(Actor.id == actor_id)).scalar_one_or_none()
    if not a:
        return {"error": "actor_not_found"}
    p = db.execute(select(ActorProfile).where(ActorProfile.actor_id == actor_id)).scalar_one_or_none()
    if not p:
        return {"actor_id": actor_id, "profile": None}
    return {
        "actor_id": actor_id,
        "profile": {
            "pronouns": p.pronouns,
            "voice": p.voice,
            "faction": p.faction,
            "appearance": p.appearance,
            "personality": p.personality,
            "mannerisms": p.mannerisms,
            "backstory": p.backstory,
            "goals": p.goals,
            "secrets": p.secrets,
            "age": p.age,
            "species": p.species,
            "occupation": p.occupation,
            "alignment": p.alignment,
            "extra": p.extra or {},
        },
    }


@router.put("/profiles/{actor_id}")
def upsert_profile(actor_id: str, data: ActorProfileUpsertIn, db: Session = Depends(get_db)):
    a = db.execute(select(Actor).where(Actor.id == actor_id)).scalar_one_or_none()
    if not a:
        return {"error": "actor_not_found"}

    p = db.execute(select(ActorProfile).where(ActorProfile.actor_id == actor_id)).scalar_one_or_none()
    if not p:
        p = ActorProfile(actor_id=actor_id)
        db.add(p)
        db.flush()

    payload = data.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(p, k, v)
    db.commit()
    return {"status": "ok", "actor_id": actor_id}
