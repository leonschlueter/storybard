from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.scene import Scene
from app.models.world import WorldNode
from app.models.actor import Actor, ActorKind
from app.models.actor_profile import ActorProfile


router = APIRouter()


class SceneUpdateIn(BaseModel):
    title: str | None = None
    summary: str | None = None
    current_node_id: str | None = None
    npc_ids: list[str] | None = None
    location_ids: list[str] | None = None
    world_info: str | None = None
    nearby_info: str | None = None


@router.get("/scene/{campaign_id}")
def get_scene(campaign_id: str, db: Session = Depends(get_db)):
    scene = db.execute(
        select(Scene).where(Scene.campaign_id == campaign_id, Scene.is_current == True)  # noqa: E712
    ).scalar_one_or_none()
    if not scene:
        scene = Scene(campaign_id=campaign_id, is_current=True)
        db.add(scene)
        db.commit()
        db.refresh(scene)
    current_node = None
    if scene.current_node_id:
        current_node = db.execute(select(WorldNode).where(WorldNode.id == scene.current_node_id)).scalar_one_or_none()

    # NPCs present (full sheets)
    npcs_present: list[dict] = []
    if scene.npc_ids:
        rows = db.execute(
            select(Actor, ActorProfile)
            .join(ActorProfile, ActorProfile.actor_id == Actor.id, isouter=True)
            .where(Actor.id.in_(scene.npc_ids))
        ).all()
        for a, p in rows:
            npcs_present.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "bio": a.bio,
                    "pronouns": (p.pronouns if p else None),
                    "species": (p.extra.get("species") if p and p.extra else None),
                    "age": (p.extra.get("age") if p and p.extra else None),
                    "occupation": (p.extra.get("occupation") if p and p.extra else None),
                    "alignment": (p.extra.get("alignment") if p and p.extra else None),
                    "appearance": (p.appearance if p else None),
                    "personality": (p.personality if p else None),
                    "mannerisms": (p.mannerisms if p else None),
                    "backstory": (p.backstory if p else None),
                }
            )

    # Nearby locations (coordinate-based)
    nearby_locations: list[dict] = []
    if current_node and current_node.x is not None and current_node.y is not None:
        nodes = (
            db.execute(select(WorldNode).where(WorldNode.campaign_id == campaign_id)).scalars().all()
        )
        for n in nodes:
            if not n.x or not n.y or n.id == current_node.id:
                continue
            dx = float(n.x) - float(current_node.x)
            dy = float(n.y) - float(current_node.y)
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > 20:
                continue

            npcs = (
                db.execute(
                    select(Actor)
                    .where(
                        Actor.campaign_id == campaign_id,
                        Actor.kind == ActorKind.npc.value,
                        Actor.current_node_id == n.id,
                    )
                    .limit(5)
                )
                .scalars()
                .all()
            )

            nearby_locations.append(
                {
                    "id": n.id,
                    "name": n.name,
                    "short_description": n.description,
                    "minutes": max(1, int(round(dist * 2.5))),
                    "npcs": [{"id": a.id, "name": a.name, "bio": a.bio} for a in npcs],
                }
            )

        nearby_locations.sort(key=lambda x: x["minutes"])
        nearby_locations = nearby_locations[:8]

    return {
        "id": scene.id,
        "campaign_id": scene.campaign_id,
        "title": scene.title,
        "summary": scene.summary,
        "current_node_id": scene.current_node_id,
        "npc_ids": scene.npc_ids,
        "location_ids": scene.location_ids,
        "world_info": scene.world_info,
        "nearby_info": scene.nearby_info,
        "current_location": (
            {
                "id": current_node.id,
                "name": current_node.name,
                "description": current_node.description_long or current_node.description,
                "x": current_node.x,
                "y": current_node.y,
            }
            if current_node
            else None
        ),
        "nearby_locations": nearby_locations,
        "npcs_present": npcs_present,
        "updated_at": scene.updated_at.isoformat() if scene.updated_at else None,
    }


@router.put("/scene/{campaign_id}")
def update_scene(campaign_id: str, data: SceneUpdateIn, db: Session = Depends(get_db)):
    scene = db.execute(
        select(Scene).where(Scene.campaign_id == campaign_id, Scene.is_current == True)  # noqa: E712
    ).scalar_one_or_none()
    if not scene:
        scene = Scene(campaign_id=campaign_id, is_current=True)
        db.add(scene)

    for field in ("title", "summary", "current_node_id", "npc_ids", "location_ids", "world_info", "nearby_info"):
        v = getattr(data, field)
        if v is not None:
            setattr(scene, field, v)

    db.commit()
    db.refresh(scene)
    return {"status": "ok", "scene_id": scene.id}
