from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import get_db
from app.models.campaign import Campaign
from app.models.actor import Actor
from app.models.character_sheet import CharacterSheet
from app.models.event import Event
from app.models.thread import StoryThread
from app.models.context import ContextBlock

router = APIRouter()

@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    c = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
    if not c:
        return {"error":"not_found"}
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
        return {"error":"not_found"}
    s = db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id)).scalar_one_or_none()
    return {
        "id": a.id,
        "campaign_id": a.campaign_id,
        "name": a.name,
        "kind": a.kind,
        "bio": a.bio,
        "current_node_id": a.current_node_id,
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
        }
    }

@router.get("/campaigns/{campaign_id}/events")
def list_events(campaign_id: str, limit: int = 30, db: Session = Depends(get_db)):
    evs = db.execute(select(Event).where(Event.campaign_id == campaign_id).order_by(Event.created_at.desc()).limit(limit)).scalars().all()
    evs = list(reversed(evs))
    return [{
        "id": e.id,
        "campaign_timestamp": e.campaign_timestamp.isoformat(),
        "mode": e.mode,
        "action_text": e.action_text,
        "check": e.check,
        "narration": e.narration,
    } for e in evs]

@router.get("/campaigns/{campaign_id}/threads")
def list_threads(campaign_id: str, db: Session = Depends(get_db)):
    ts = db.execute(select(StoryThread).where(StoryThread.campaign_id == campaign_id).order_by(StoryThread.priority.desc())).scalars().all()
    return [{"id": t.id, "title": t.title, "summary": t.summary, "status": t.status, "priority": t.priority, "state": t.state} for t in ts]

@router.get("/campaigns/{campaign_id}/context-blocks")
def list_blocks(campaign_id: str, active_only: bool = True, db: Session = Depends(get_db)):
    q = select(ContextBlock).where(ContextBlock.campaign_id == campaign_id)
    if active_only:
        q = q.where(ContextBlock.is_active == True)
    blocks = db.execute(q.order_by(ContextBlock.priority.desc())).scalars().all()
    return [{"id": b.id, "type": b.type, "title": b.title, "scope_type": b.scope_type, "scope_id": b.scope_id, "summary": b.summary, "full_text": b.full_text, "structured": b.structured, "priority": b.priority, "ttl_turns": b.ttl_turns, "is_active": b.is_active} for b in blocks]
