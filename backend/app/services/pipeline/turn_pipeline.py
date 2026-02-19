from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.metrics import TURN_COUNTER, PIPELINE_SECONDS
from app.models.campaign import Campaign
from app.models.actor import Actor
from app.models.world import WorldNode
from app.models.event import Event
from app.models.pending_roll import PendingRoll
from app.models.context import ContextBlock
from app.models.thread import StoryThread

from app.services.llm.roles import LLMRoles
from app.services.llm.ollama_client import OllamaError
from app.services.mechanics.encumbrance import encumbrance_snapshot
from app.services.mechanics.phase_checker import PhaseChecker
from app.services.mechanics.rolls import skill_modifier, resolve_skill_check
from app.services.context.catalog import build_catalogs
from app.services.context.fetch import fetch_selected
from app.services.context.renderer import render_context_blocks, render_lore_pages, render_recent_history
from app.services.ops.apply_ops import apply_ops
from app.services.memory.decay import decay_ttl_blocks
from app.services.world.timeline import advance_time
from app.services.world.world_tick import world_tick

log = structlog.get_logger()

class TurnPipeline:
    def __init__(self, llm: LLMRoles):
        self.llm = llm
        self.phase_checker = PhaseChecker()

    def _recent_events(self, db: Session, campaign_id: str, n: int = 12) -> list[dict]:
        evs = db.execute(
            select(Event).where(Event.campaign_id == campaign_id).order_by(Event.created_at.desc()).limit(n)
        ).scalars().all()
        evs = list(reversed(evs))
        return [{"action_text": e.action_text, "narration": e.narration, "check": e.check} for e in evs]

    def _campaign_summary(self, db: Session, campaign_id: str) -> str:
        b = db.execute(
            select(ContextBlock).where(ContextBlock.campaign_id == campaign_id, ContextBlock.type == "campaign_summary")
        ).scalar_one_or_none()
        return b.summary if b else ""

    def begin_turn(self, *, db: Session, actor_id: str, text: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            actor = db.execute(select(Actor).where(Actor.id == actor_id)).scalar_one_or_none()
            if not actor:
                return {"status":"error", "error":"actor_not_found"}

            camp = db.execute(select(Campaign).where(Campaign.id == actor.campaign_id)).scalar_one()
            location = None
            if actor.current_node_id:
                location = db.execute(select(WorldNode).where(WorldNode.id == actor.current_node_id)).scalar_one_or_none()

            # decay TTL blocks every turn
            decay_ttl_blocks(db, camp.id)

            mech = encumbrance_snapshot(db, actor.id)

            # Intent + check advice
            intent = self.llm.parse_intent(player_text=text, mode=camp.mode)
            check_advice = self.llm.advise_check(
                player_text=text,
                mode=camp.mode,
                mechanics_snapshot=mech,
                location_name=(location.name if location else None),
            )

            decision = self.phase_checker.decide(mode=camp.mode, intent=intent, check_advice=check_advice)

            # Mode change (deterministic)
            if decision.phase.value == "mode_change" and decision.mode_change_to:
                old = camp.mode
                camp.mode = decision.mode_change_to
                db.commit()
                return {
                    "status":"ok",
                    "phase": "mode_change",
                    "campaign_id": camp.id,
                    "actor_id": actor.id,
                    "mode": camp.mode,
                    "campaign_time": camp.current_datetime.isoformat(),
                    "narration": f"Mode changed from {old} to {camp.mode}.",
                    "debug": {"intent": intent.model_dump(), "check_advice": check_advice.model_dump()},
                }

            # Roll required => create pending roll and return
            if decision.phase.value in ("skill_check_required","initiative_required"):
                mod = 0
                details = {}
                if decision.roll_type and decision.roll_type.value == "skill_check":
                    mod, details = skill_modifier(db, actor.id, decision.skill or "perception")

                pr = PendingRoll(
                    campaign_id=camp.id,
                    actor_id=actor.id,
                    roll_type=(decision.roll_type.value if decision.roll_type else "skill_check"),
                    skill=decision.skill,
                    dc=decision.dc,
                    dc_reason=decision.dc_reason,
                    action_text=text,
                    intent=intent.model_dump(),
                    modifier=mod,
                    details=details,
                    resolved=False,
                )
                db.add(pr)
                # advance time for attempt initiation (optional)
                if decision.time_passed_minutes:
                    camp.current_datetime = advance_time(camp.current_datetime, decision.time_passed_minutes)
                db.commit()

                return {
                    "status":"ok",
                    "phase": decision.phase.value,
                    "campaign_id": camp.id,
                    "actor_id": actor.id,
                    "mode": camp.mode,
                    "campaign_time": camp.current_datetime.isoformat(),
                    "pending_roll": {
                        "id": pr.id,
                        "roll_type": pr.roll_type,
                        "skill": pr.skill,
                        "dc": pr.dc,
                        "dc_reason": pr.dc_reason,
                        "modifier": pr.modifier,
                        "modifier_details": pr.details,
                        "prompt": f"Roll a d20 for {pr.skill or 'initiative'} (DC {pr.dc}). Enter the raw d20 result.",
                    },
                    "debug": {"intent": intent.model_dump(), "check_advice": check_advice.model_dump()},
                }

            # No roll required => proceed to planning+narration
            # Knowledge selection
            catalogs = build_catalogs(db, camp.id)
            selection = self.llm.select_knowledge(player_text=text, mode=camp.mode, catalogs=catalogs)

            fetched = fetch_selected(db, selection.model_dump())

            # Build narrator payload (Strategy B)
            threads = db.execute(select(StoryThread).where(StoryThread.campaign_id == camp.id, StoryThread.status == "active").order_by(StoryThread.priority.desc()).limit(6)).scalars().all()
            threads_payload = [{"id": t.id, "title": t.title, "summary": t.summary, "status": t.status, "priority": t.priority, "state": t.state} for t in threads]

            recent = self._recent_events(db, camp.id, n=12)

            payload = {
                "campaign_info": {
                    "id": camp.id,
                    "name": camp.name,
                    "mode": camp.mode,
                    "calendar": camp.calendar_name,
                    "start_datetime": camp.start_datetime.isoformat(),
                    "current_datetime": camp.current_datetime.isoformat(),
                    "tone_profile": camp.tone_profile,
                    "reskin_profile": camp.reskin_profile,
                    "setting_tags": camp.setting_tags,
                },
                "narration_style": camp.narration_style,
                "campaign_summary": self._campaign_summary(db, camp.id),
                "threads": threads_payload,
                "mechanics_snapshot": mech,
                "context_blocks_text": render_context_blocks(fetched.get("context_blocks", [])),
                "lore_pages_text": render_lore_pages(fetched.get("lore_pages", [])),
                "recent_history_text": render_recent_history(recent),
                "player_text": text,
                "check_result": {},
            }

            # GM planner (ops + time)
            gm_payload = {
                "campaign": payload["campaign_info"],
                "player": {"id": actor.id, "name": actor.name},
                "location": {"id": location.id, "name": location.name} if location else None,
                "mode": camp.mode,
                "player_text": text,
                "intent": intent.model_dump(),
                "mechanics_snapshot": mech,
                "threads": threads_payload,
                "fetched": fetched,
                "constraints": {"max_ops": 10},
            }
            gm_out = self.llm.gm_plan(payload=gm_payload)

            # Apply GM ops
            with db.begin():
                created = apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in gm_out.ops])

            # Refresh fetched payload to include newly created entities in narration context
            if created:
                selection_dict = selection.model_dump()
                for k, ids in created.items():
                    # map created buckets to selection keys where possible
                    if k == "context_blocks":
                        selection_dict["context_blocks"] = list(dict.fromkeys(selection_dict.get("context_blocks", []) + ids))
                    elif k == "lore_pages":
                        selection_dict["lore_pages"] = list(dict.fromkeys(selection_dict.get("lore_pages", []) + ids))
                    elif k == "world_nodes":
                        selection_dict["world_nodes"] = list(dict.fromkeys(selection_dict.get("world_nodes", []) + ids))
                    elif k == "actors":
                        selection_dict["actors"] = list(dict.fromkeys(selection_dict.get("actors", []) + ids))
                    elif k == "threads":
                        selection_dict["threads"] = list(dict.fromkeys(selection_dict.get("threads", []) + ids))
                    elif k == "item_defs":
                        selection_dict["item_defs"] = list(dict.fromkeys(selection_dict.get("item_defs", []) + ids))
                    elif k == "spell_defs":
                        selection_dict["spell_defs"] = list(dict.fromkeys(selection_dict.get("spell_defs", []) + ids))
                fetched = fetch_selected(db, selection_dict)
                # Update narrator context sections with refreshed fetches
                narrator_payload["context_blocks_text"] = render_context_blocks(fetched.get("context_blocks", []))
                narrator_payload["lore_pages_text"] = render_lore_pages(fetched.get("lore_pages", []))
                # Update narrator context sections with refreshed fetches
                payload["context_blocks_text"] = render_context_blocks(fetched.get("context_blocks", []))
                payload["lore_pages_text"] = render_lore_pages(fetched.get("lore_pages", []))

            # Time advance
            if gm_out.time_passed_minutes:
                camp.current_datetime = advance_time(camp.current_datetime, gm_out.time_passed_minutes)

            # Narrate
            narration = self.llm.narrate(payload=payload)

            # Persist event + increment turn count
            with db.begin():
                ev = Event(
                    campaign_id=camp.id,
                    actor_id=actor.id,
                    campaign_timestamp=camp.current_datetime,
                    mode=camp.mode,
                    action_text=text,
                    intent=intent.model_dump(),
                    check={},
                    narration=narration.narration,
                    result_data={"gm_notes": gm_out.gm_notes},
                )
                db.add(ev)
                camp.turn_count += 1

            # Memory regression every turn
            self._memory_regress(db, camp, actor, location, ev)

            # Campaign summary every 5 turns
            if camp.turn_count % 5 == 0:
                self._update_campaign_summary(db, camp)

            # Thread advancement every 3 turns
            if camp.turn_count % 3 == 0:
                self._advance_threads(db, camp)

            # World tick
            world_tick(db, camp.id, 0)

            db.commit()
            TURN_COUNTER.labels(result="ok").inc()
            return {
                "status":"ok",
                "phase":"narrative",
                "campaign_id": camp.id,
                "actor_id": actor.id,
                "mode": camp.mode,
                "campaign_time": camp.current_datetime.isoformat(),
                "narration": narration.narration,
                "debug": {
                    "intent": intent.model_dump(),
                    "check_advice": check_advice.model_dump(),
                    "knowledge": selection.model_dump(),
                    "gm": gm_out.model_dump(),
                },
            }

        except OllamaError as e:
            TURN_COUNTER.labels(result="llm_error").inc()
            log.exception("ollama_error", error=str(e))
            return {"status":"error", "error":"ollama_error", "detail": str(e)}
        except Exception as e:
            TURN_COUNTER.labels(result="error").inc()
            log.exception("turn_error", error=str(e))
            return {"status":"error", "error":"turn_error", "detail": str(e)}
        finally:
            PIPELINE_SECONDS.observe(time.perf_counter() - t0)

    def resolve_roll(self, *, db: Session, pending_roll_id: str, d20: int) -> dict[str, Any]:
        t0 = time.perf_counter()
        try:
            pr = db.execute(select(PendingRoll).where(PendingRoll.id == pending_roll_id)).scalar_one_or_none()
            if not pr:
                return {"status":"error", "error":"pending_roll_not_found"}
            if pr.resolved:
                return {"status":"error", "error":"pending_roll_already_resolved"}

            actor = db.execute(select(Actor).where(Actor.id == pr.actor_id)).scalar_one()
            camp = db.execute(select(Campaign).where(Campaign.id == pr.campaign_id)).scalar_one()
            location = None
            if actor.current_node_id:
                location = db.execute(select(WorldNode).where(WorldNode.id == actor.current_node_id)).scalar_one_or_none()

            mech = encumbrance_snapshot(db, actor.id)

            # Resolve roll
            check_result: dict[str, Any] = {}
            if pr.roll_type == "skill_check":
                dc = int(pr.dc or 15)
                total, outcome = resolve_skill_check(d20=d20, modifier=int(pr.modifier), dc=dc)
                pr.d20 = int(d20)
                pr.total = total
                pr.outcome = outcome
                check_result = {
                    "roll_type": "skill_check",
                    "skill": pr.skill,
                    "dc": dc,
                    "dc_reason": pr.dc_reason,
                    "d20": int(d20),
                    "modifier": int(pr.modifier),
                    "total": total,
                    "outcome": outcome,
                    "modifier_details": pr.details,
                }
            else:
                # initiative request stub
                pr.d20 = int(d20)
                pr.total = int(d20)  # no modifier for now
                pr.outcome = "ok"
                check_result = {"roll_type":"initiative", "d20": int(d20), "total": int(d20), "outcome":"ok"}

            pr.resolved = True
            pr.resolved_at = datetime.utcnow()

            # Knowledge selection for completion
            catalogs = build_catalogs(db, camp.id)
            selection = self.llm.select_knowledge(player_text=pr.action_text, mode=camp.mode, catalogs=catalogs)
            fetched = fetch_selected(db, selection.model_dump())

            threads = db.execute(select(StoryThread).where(StoryThread.campaign_id == camp.id, StoryThread.status == "active").order_by(StoryThread.priority.desc()).limit(6)).scalars().all()
            threads_payload = [{"id": t.id, "title": t.title, "summary": t.summary, "status": t.status, "priority": t.priority, "state": t.state} for t in threads]

            recent = self._recent_events(db, camp.id, n=12)

            narrator_payload = {
                "campaign_info": {
                    "id": camp.id,
                    "name": camp.name,
                    "mode": camp.mode,
                    "calendar": camp.calendar_name,
                    "start_datetime": camp.start_datetime.isoformat(),
                    "current_datetime": camp.current_datetime.isoformat(),
                    "tone_profile": camp.tone_profile,
                    "reskin_profile": camp.reskin_profile,
                    "setting_tags": camp.setting_tags,
                },
                "narration_style": camp.narration_style,
                "campaign_summary": self._campaign_summary(db, camp.id),
                "threads": threads_payload,
                "mechanics_snapshot": mech,
                "context_blocks_text": render_context_blocks(fetched.get("context_blocks", [])),
                "lore_pages_text": render_lore_pages(fetched.get("lore_pages", [])),
                "recent_history_text": render_recent_history(recent),
                "player_text": pr.action_text,
                "check_result": check_result,
            }

            gm_payload = {
                "campaign": narrator_payload["campaign_info"],
                "player": {"id": actor.id, "name": actor.name},
                "location": {"id": location.id, "name": location.name} if location else None,
                "mode": camp.mode,
                "player_text": pr.action_text,
                "intent": pr.intent,
                "mechanics_snapshot": mech,
                "check_result": check_result,
                "threads": threads_payload,
                "fetched": fetched,
                "constraints": {"max_ops": 12},
            }
            gm_out = self.llm.gm_plan(payload=gm_payload)

            with db.begin():
                created = apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in gm_out.ops])

            # Refresh fetched payload to include newly created entities in narration context
            if created:
                selection_dict = selection.model_dump()
                for k, ids in created.items():
                    # map created buckets to selection keys where possible
                    if k == "context_blocks":
                        selection_dict["context_blocks"] = list(dict.fromkeys(selection_dict.get("context_blocks", []) + ids))
                    elif k == "lore_pages":
                        selection_dict["lore_pages"] = list(dict.fromkeys(selection_dict.get("lore_pages", []) + ids))
                    elif k == "world_nodes":
                        selection_dict["world_nodes"] = list(dict.fromkeys(selection_dict.get("world_nodes", []) + ids))
                    elif k == "actors":
                        selection_dict["actors"] = list(dict.fromkeys(selection_dict.get("actors", []) + ids))
                    elif k == "threads":
                        selection_dict["threads"] = list(dict.fromkeys(selection_dict.get("threads", []) + ids))
                    elif k == "item_defs":
                        selection_dict["item_defs"] = list(dict.fromkeys(selection_dict.get("item_defs", []) + ids))
                    elif k == "spell_defs":
                        selection_dict["spell_defs"] = list(dict.fromkeys(selection_dict.get("spell_defs", []) + ids))
                fetched = fetch_selected(db, selection_dict)

            if gm_out.time_passed_minutes:
                camp.current_datetime = advance_time(camp.current_datetime, gm_out.time_passed_minutes)

            narration = self.llm.narrate(payload=narrator_payload)

            with db.begin():
                ev = Event(
                    campaign_id=camp.id,
                    actor_id=actor.id,
                    campaign_timestamp=camp.current_datetime,
                    mode=camp.mode,
                    action_text=pr.action_text,
                    intent=pr.intent,
                    check=check_result,
                    narration=narration.narration,
                    result_data={"gm_notes": gm_out.gm_notes},
                )
                db.add(ev)
                camp.turn_count += 1

            self._memory_regress(db, camp, actor, location, ev)
            if camp.turn_count % 5 == 0:
                self._update_campaign_summary(db, camp)
            if camp.turn_count % 3 == 0:
                self._advance_threads(db, camp)

            db.commit()
            TURN_COUNTER.labels(result="ok").inc()
            return {
                "status":"ok",
                "phase":"narrative",
                "campaign_id": camp.id,
                "actor_id": actor.id,
                "mode": camp.mode,
                "campaign_time": camp.current_datetime.isoformat(),
                "narration": narration.narration,
                "check_result": check_result,
                "debug": {
                    "knowledge": selection.model_dump(),
                    "gm": gm_out.model_dump(),
                },
            }

        except OllamaError as e:
            TURN_COUNTER.labels(result="llm_error").inc()
            log.exception("ollama_error", error=str(e))
            return {"status":"error", "error":"ollama_error", "detail": str(e)}
        except Exception as e:
            TURN_COUNTER.labels(result="error").inc()
            log.exception("roll_error", error=str(e))
            return {"status":"error", "error":"roll_error", "detail": str(e)}
        finally:
            PIPELINE_SECONDS.observe(time.perf_counter() - t0)

    def _memory_regress(self, db: Session, camp: Campaign, actor: Actor, location: WorldNode | None, ev: Event) -> None:
        payload = {
            "campaign_id": camp.id,
            "event": {"action_text": ev.action_text, "narration": ev.narration, "check": ev.check},
            "player": {"id": actor.id, "name": actor.name},
            "location": {"id": location.id, "name": location.name} if location else None,
            "constraints": {"max_ops": 6},
        }
        try:
            mem_out = self.llm.regress_memory(payload=payload)
        except Exception:
            return

        with db.begin():
            apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in mem_out.ops])

    def _update_campaign_summary(self, db: Session, camp: Campaign) -> None:
        # summarize last 5 events into the campaign_summary context block
        last5 = db.execute(
            select(Event).where(Event.campaign_id == camp.id).order_by(Event.created_at.desc()).limit(5)
        ).scalars().all()
        last5 = list(reversed(last5))
        transcript = []
        for e in last5:
            transcript.append({"player": e.action_text, "narrator": e.narration, "check": e.check})

        payload = {
            "campaign_name": camp.name,
            "turn_count": camp.turn_count,
            "last_5": transcript,
            "instruction": "Write a concise campaign summary update (4-8 sentences) capturing what just happened and any open leads.",
            "constraints": {"max_ops": 2},
        }

        # Reuse GM planner schema by emitting update_context_block op
        try:
            out = self.llm.gm_plan(payload=payload)
        except Exception:
            return

        # Find existing summary block
        b = db.execute(select(ContextBlock).where(ContextBlock.campaign_id == camp.id, ContextBlock.type == "campaign_summary")).scalar_one_or_none()
        if not b:
            b = ContextBlock(
                campaign_id=camp.id,
                type="campaign_summary",
                title="Campaign Summary",
                scope_type="global",
                visibility="player",
                hardness="hard",
                summary="",
                priority=1.0,
                is_active=True,
                structured={"last_summarized_turn": 0},
            )
            db.add(b)
            db.flush()

        # If LLM produced update ops, apply; otherwise treat gm_notes as summary
        applied = False
        for op in out.ops:
            if op.op == "update_context_block":
                applied = True
        if out.ops and applied:
            with db.begin():
                apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in out.ops])
        else:
            b.summary = (b.summary + "\n\n" + " ".join(out.gm_notes)).strip()[:5000]

        b.structured = dict(b.structured or {})
        b.structured["last_summarized_turn"] = camp.turn_count
        db.commit()

    def _advance_threads(self, db: Session, camp: Campaign) -> None:
        threads = db.execute(select(StoryThread).where(StoryThread.campaign_id == camp.id).order_by(StoryThread.priority.desc()).limit(8)).scalars().all()
        threads_payload = [{"id": t.id, "title": t.title, "summary": t.summary, "status": t.status, "priority": t.priority, "state": t.state} for t in threads]

        last_events = db.execute(select(Event).where(Event.campaign_id == camp.id).order_by(Event.created_at.desc()).limit(6)).scalars().all()
        last_events = list(reversed(last_events))
        ev_payload = [{"action_text": e.action_text, "narration": e.narration, "check": e.check} for e in last_events]

        payload = {
            "campaign_id": camp.id,
            "turn_count": camp.turn_count,
            "threads": threads_payload,
            "recent_events": ev_payload,
            "constraints": {"max_ops": 10},
        }
        try:
            out = self.llm.advance_threads(payload=payload)
        except Exception:
            return
        with db.begin():
            apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in out.ops])
