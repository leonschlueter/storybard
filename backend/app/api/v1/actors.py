from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.actor import (
    Actor,
    ActorAbilityScores,
    ActorClass,
    ActorResource,
)
from app.models.world import WorldNode

router = APIRouter()


@router.post("/")
def create_actor(campaign_id: str, db: Session = Depends(get_db)):
    # Find tavern
    tavern = (
        db.query(WorldNode)
        .filter(WorldNode.campaign_id == campaign_id)
        .filter(WorldNode.name == "The Rusty Flagon")
        .first()
    )

    actor = Actor(
        campaign_id=campaign_id,
        type="player",
        name="Arthas",
        race="Human",
        alignment="Neutral Good",
        background="Soldier",
        level_total=1,
        xp=0,
        hp_current=12,
        hp_max=12,
        current_node_id=tavern.id if tavern else None,
    )
    db.add(actor)
    db.commit()
    db.refresh(actor)

    # Ability scores
    scores = ActorAbilityScores(
        actor_id=actor.id,
        strength=16,
        dexterity=12,
        constitution=14,
        intelligence=10,
        wisdom=11,
        charisma=13,
    )
    db.add(scores)

    # Class
    fighter = ActorClass(
        actor_id=actor.id,
        class_name="Fighter",
        subclass_name=None,
        level=1,
    )
    db.add(fighter)

    # Resources
    resources = ActorResource(
        actor_id=actor.id,
        gold=10,
        exhaustion_level=0,
        inspiration=False,
    )
    db.add(resources)

    db.commit()

    return {
        "actor_id": str(actor.id),
        "name": actor.name,
        "class": "Fighter",
    }
