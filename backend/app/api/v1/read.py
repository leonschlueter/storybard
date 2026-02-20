from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.actor import Actor
from app.models.actor_profile import ActorProfile
from app.models.character_sheet import CharacterSheet
from app.models.event import Event
from app.models.thread import StoryThread
from app.models.context import ContextBlock
from app.models.world import WorldNode
from app.models.scene import Scene
from app.models.memory import Memory

router = APIRouter()


def _serialize_profile(p: ActorProfile | None) -> dict | None:
    if not p:
        return None
    return {
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
    }


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
    if not c:
        return {"error": "not_found"}
    return {
        "id": c.id,
        "name": c.name,
        "mode": c.mode,
        "narration_style": c.narration_style,
        "calendar": c.calendar_name,
        "start_datetime": c.start_datetime.isoformat(),
        "current_datetime": c.current_datetime.isoformat(),
        "turn_count": c.turn_count,
        "tone_profile": c.tone_profile,
        "reskin_profile": c.reskin_profile,
        "setting_tags": c.setting_tags,
    }


@router.get("/actors/{actor_id}")
def get_actor(actor_id: str, db: Session = Depends(get_db)):
    a = db.execute(select(Actor).where(Actor.id == actor_id)).scalar_one_or_none()
    if not a:
        return {"error": "not_found"}

    s = db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id)).scalar_one_or_none()
    p = db.execute(select(ActorProfile).where(ActorProfile.actor_id == actor_id)).scalar_one_or_none()
    mems = (
        db.execute(
            select(Memory)
            .where(Memory.owner_actor_id == actor_id)
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
            .limit(25)
        )
        .scalars()
        .all()
    )

    return {
        "id": a.id,
        "campaign_id": a.campaign_id,
        "name": a.name,
        "kind": a.kind,
        "bio": a.bio,
        "current_node_id": a.current_node_id,
        "profile": _serialize_profile(p),
        "sheet": None if not s else {
            "level": s.level,
            "class_name": s.class_name,
            "race": s.race,
            "background": s.background,
            "ability_scores": s.ability_scores,
            "proficiencies": s.proficiencies,
            "max_hp": s.max_hp,
            "current_hp": s.current_hp,
            "speed": s.speed,
            "gold": s.gold,
            "spell_slots": s.spell_slots,
            "conditions": s.conditions,
        },
        "memories": [
            {
                "id": m.id,
                "subject_actor_id": m.subject_actor_id,
                "title": m.title,
                "text": m.text,
                "importance": m.importance,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in mems
        ],
    }


@router.get("/campaigns/{campaign_id}/actors")
def list_actors(campaign_id: str, kind: str | None = None, db: Session = Depends(get_db)):
    q = select(Actor).where(Actor.campaign_id == campaign_id)
    if kind:
        q = q.where(Actor.kind == kind)
    actors = db.execute(q.order_by(Actor.name.asc())).scalars().all()
    actor_ids = [a.id for a in actors]
    profs = (
        db.execute(select(ActorProfile).where(ActorProfile.actor_id.in_(actor_ids))).scalars().all()
        if actor_ids
        else []
    )
    prof_map = {p.actor_id: p for p in profs}
    return [
        {
            "id": a.id,
            "name": a.name,
            "kind": a.kind,
            "bio": a.bio,
            "current_node_id": a.current_node_id,
            "profile": _serialize_profile(prof_map.get(a.id)),
        }
        for a in actors
    ]


@router.get("/campaigns/{campaign_id}/world-nodes")
def list_world_nodes(campaign_id: str, db: Session = Depends(get_db)):
    nodes = db.execute(select(WorldNode).where(WorldNode.campaign_id == campaign_id).order_by(WorldNode.name.asc())).scalars().all()
    return [
        {
            "id": n.id,
            "name": n.name,
            "description": n.description,
            "tags": n.tags,
            "x": n.x,
            "y": n.y,
        }
        for n in nodes
    ]


@router.get("/campaigns/{campaign_id}/events")
def list_events(campaign_id: str, limit: int = 30, db: Session = Depends(get_db)):
    evs = db.execute(select(Event).where(Event.campaign_id == campaign_id).order_by(Event.created_at.desc()).limit(limit)).scalars().all()
    evs = list(reversed(evs))
    return [
        {
            "id": e.id,
            "campaign_timestamp": e.campaign_timestamp.isoformat(),
            "mode": e.mode,
            "action_text": e.action_text,
            "check": e.check,
            "narration": e.narration,
            "result_data": e.result_data,
        }
        for e in evs
    ]


@router.get("/campaigns/{campaign_id}/thoughts")
def list_thoughts(campaign_id: str, limit: int = 10, db: Session = Depends(get_db)):
    evs = (
        db.execute(select(Event).where(Event.campaign_id == campaign_id).order_by(Event.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    out = []
    for e in evs:
        gm = (e.result_data or {}).get("gm_thoughts") or {}
        if not gm:
            continue
        out.append(
            {
                "event_id": e.id,
                "campaign_timestamp": e.campaign_timestamp.isoformat() if e.campaign_timestamp else None,
                "introspection": gm.get("introspection", ""),
                "pacing": gm.get("pacing", ""),
                "plan": gm.get("plan", ""),
                "world_facts": gm.get("world_facts", []),
                "scene_focus": gm.get("scene_focus", []),
            }
        )
    return list(reversed(out))


@router.get("/campaigns/{campaign_id}/threads")
def list_threads(campaign_id: str, db: Session = Depends(get_db)):
    ts = db.execute(select(StoryThread).where(StoryThread.campaign_id == campaign_id).order_by(StoryThread.priority.desc())).scalars().all()
    return [{"id": t.id, "title": t.title, "summary": t.summary, "status": t.status, "priority": t.priority, "state": t.state} for t in ts]


@router.get("/campaigns/{campaign_id}/plot-summary")
def get_plot_summary(campaign_id: str, db: Session = Depends(get_db)):
    b = db.execute(
        select(ContextBlock).where(ContextBlock.campaign_id == campaign_id, ContextBlock.type == "plot_summary")
    ).scalar_one_or_none()
    if not b:
        return {"title": "Plot Summary", "summary": ""}
    return {
        "id": b.id,
        "title": b.title or "Plot Summary",
        "summary": b.full_text or b.summary or "",
    }


@router.get("/campaigns/{campaign_id}/context-blocks")
def list_blocks(campaign_id: str, active_only: bool = True, db: Session = Depends(get_db)):
    q = select(ContextBlock).where(ContextBlock.campaign_id == campaign_id)
    if active_only:
        q = q.where(ContextBlock.is_active == True)  # noqa: E712
    blocks = db.execute(q.order_by(ContextBlock.priority.desc())).scalars().all()
    return [
        {
            "id": b.id,
            "type": b.type,
            "title": b.title,
            "scope_type": b.scope_type,
            "scope_id": b.scope_id,
            "summary": b.summary,
            "full_text": b.full_text,
            "structured": b.structured,
            "priority": b.priority,
            "ttl_turns": b.ttl_turns,
            "is_active": b.is_active,
        }
        for b in blocks
    ]


@router.get("/campaigns/{campaign_id}/scene")
def read_current_scene(campaign_id: str, db: Session = Depends(get_db)):
    s = db.execute(select(Scene).where(Scene.campaign_id == campaign_id, Scene.is_current == True)).scalar_one_or_none()  # noqa: E712
    if not s:
        return {"error": "not_found"}
    return {
        "id": s.id,
        "title": s.title,
        "summary": s.summary,
        "world_info": s.world_info,
        "nearby_info": s.nearby_info,
        "current_node_id": s.current_node_id,
        "npc_ids": s.npc_ids or [],
        "location_ids": s.location_ids or [],
    }
