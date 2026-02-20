from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings

from app.core.metrics import TURN_COUNTER, PIPELINE_SECONDS
from app.models.campaign import Campaign
from app.models.actor import Actor
from app.models.world import WorldNode
from app.models.event import Event
from app.models.pending_roll import PendingRoll
from app.models.context import ContextBlock
from app.models.scene import Scene

from app.services.llm.roles import LLMRoles
from app.services.llm.ollama_client import OllamaError
from app.services.mechanics.encumbrance import encumbrance_snapshot
from app.services.mechanics.phase_checker import PhaseChecker
from app.services.mechanics.rolls import skill_modifier, resolve_skill_check
from app.services.context.fetch import fetch_selected
from app.services.context.renderer import (
    render_context_blocks,
    render_current_scene,
)
from app.services.context.transcript import build_transcript
from app.services.lore.retriever import retrieve_lore_chunks
from app.services.ops.apply_ops import apply_ops
from app.services.memory.decay import decay_ttl_blocks
from app.services.world.timeline import advance_time
from app.services.world.world_tick import world_tick

log = structlog.get_logger()


class TurnPipeline:
    def __init__(self, llm: LLMRoles):
        self.llm = llm
        self.phase_checker = PhaseChecker()

    # ------------------------------------------------------------------ #
    # BEGIN TURN
    # ------------------------------------------------------------------ #

    def _get_current_scene(self, db: Session, campaign_id: str) -> Scene:
        scene = db.execute(
            select(Scene).where(Scene.campaign_id == campaign_id, Scene.is_current == True)  # noqa: E712
        ).scalar_one_or_none()
        if not scene:
            scene = Scene(campaign_id=campaign_id, is_current=True)
            db.add(scene)
            db.flush()
        return scene

    def begin_turn(self, *, db: Session, actor_id: str, text: str) -> dict[str, Any]:
        t0 = time.perf_counter()

        try:
            actor = db.execute(select(Actor).where(Actor.id == actor_id)).scalar_one_or_none()
            if not actor:
                return {"status": "error", "error": "actor_not_found"}

            camp = db.execute(select(Campaign).where(Campaign.id == actor.campaign_id)).scalar_one()
            location = None
            if actor.current_node_id:
                location = db.execute(
                    select(WorldNode).where(WorldNode.id == actor.current_node_id)
                ).scalar_one_or_none()

            decay_ttl_blocks(db, camp.id)

            mech = encumbrance_snapshot(db, actor.id)

            intent = self.llm.parse_intent(player_text=text, mode=camp.mode)
            check_advice = self.llm.advise_check(
                player_text=text,
                mode=camp.mode,
                mechanics_snapshot=mech,
                location_name=(location.name if location else None),
            )

            decision = self.phase_checker.decide(
                mode=camp.mode, intent=intent, check_advice=check_advice
            )

            # -------------------- Roll Required -------------------- #

            if decision.phase.value in ("skill_check_required", "initiative_required"):
                mod = 0
                details = {}

                if decision.roll_type and decision.roll_type.value == "skill_check":
                    mod, details = skill_modifier(db, actor.id, decision.skill or "perception")

                pr = PendingRoll(
                    campaign_id=camp.id,
                    actor_id=actor.id,
                    roll_type=decision.roll_type.value if decision.roll_type else "skill_check",
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
                db.flush()

                if decision.time_passed_minutes:
                    camp.current_datetime = advance_time(
                        camp.current_datetime, decision.time_passed_minutes
                    )

                return {
                    "status": "ok",
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
                    },
                }

            # -------------------- Director + World + Narration -------------------- #

            # Baseline: narrator sees scene + transcript (+ optional TTL context cards).
            scene = self._get_current_scene(db, camp.id)
            sel = {
                "world_nodes": list(
                    dict.fromkeys(
                        [x for x in ([scene.current_node_id] + list(scene.location_ids or [])) if x]
                    )
                ),
                "actors": list(dict.fromkeys(list(scene.npc_ids or []))),
                "context_blocks": [],
                "lore_pages": [],
                "threads": [],
                "item_defs": [],
                "spell_defs": [],
            }
            fetched = fetch_selected(db, sel)

            transcript_text = build_transcript(db, campaign_id=camp.id)

            payload = {
                "campaign_info": {
                    "id": camp.id,
                    "name": camp.name,
                    "mode": camp.mode,
                    "current_datetime": camp.current_datetime.isoformat(),
                },
                "mechanics_snapshot": mech,
                "context_blocks_text": "",
                "scene_text": "",  # filled below
                "transcript_text": transcript_text,
                "player_text": text,
                "check_result": {},
            }

            # Render current scene text for narrator (Friends & Fables style default context)
            payload["scene_text"] = render_current_scene(
                scene=scene,
                fetched=fetched,
            )

            gm_payload = {
                "campaign": payload["campaign_info"],
                "player": {"id": actor.id, "name": actor.name},
                "mode": camp.mode,
                "player_text": text,
                "intent": intent.model_dump(),
                "mechanics_snapshot": mech,
                "scene": {
                    "id": scene.id,
                    "title": scene.title,
                    "summary": scene.summary,
                    "current_node_id": scene.current_node_id,
                    "npc_ids": scene.npc_ids,
                    "location_ids": scene.location_ids,
                },
                "transcript": transcript_text,
                "fetched": fetched,
                "constraints": {"max_ops": 0},
            }

            gm_out = self.llm.gm_plan(payload=gm_payload)

            # Optional world building pass: create/update NPCs/locations/lore/context if needed
            world_payload = {
                "campaign": payload["campaign_info"],
                "mode": camp.mode,
                "player_text": text,
                "intent": intent.model_dump(),
                "gm_thoughts": gm_out.model_dump(),
                "scene": {
                    "id": scene.id,
                    "title": scene.title,
                    "summary": scene.summary,
                    "current_node_id": scene.current_node_id,
                    "npc_ids": scene.npc_ids,
                    "location_ids": scene.location_ids,
                },
                "fetched": fetched,
                "constraints": {"max_ops": 6},
            }
            world_out = self.llm.world_update(payload=world_payload)

            # Apply world ops safely (no nested transactions)
            if world_out.ops:
                apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in world_out.ops])
                db.flush()

            # Optional lore retrieval requested by director.
            if gm_out.retrieval_queries:
                for q in gm_out.retrieval_queries[:3]:
                    hits = retrieve_lore_chunks(db, llm=self.llm, campaign_id=camp.id, query=q)
                    for h in hits[:3]:
                        db.add(
                            ContextBlock(
                                campaign_id=camp.id,
                                type="lore_clip",
                                title=h.get("title") or "Lore",
                                scope_type="global",
                                visibility="player",
                                hardness="soft",
                                summary=(h.get("chunk_text") or "")[:400],
                                full_text=h.get("chunk_text"),
                                structured={"retrieved_for": q, "doc_type": h.get("doc_type")},
                                priority=0.55,
                                ttl_turns=int(settings.CONTEXT_BLOCK_TTL_DEFAULT_TURNS),
                                is_active=True,
                            )
                        )
                db.flush()

            # Attach active TTL context blocks (and only those) to narrator.
            ttl = (
                db.execute(
                    select(ContextBlock)
                    .where(ContextBlock.campaign_id == camp.id, ContextBlock.is_active == True)
                    .where(ContextBlock.ttl_turns.is_not(None))
                    .order_by(ContextBlock.priority.desc())
                    .limit(12)
                )
                .scalars()
                .all()
            )
            if ttl:
                payload["context_blocks_text"] = render_context_blocks(
                    [
                        {
                            "id": x.id,
                            "type": x.type,
                            "title": x.title,
                            "scope_type": x.scope_type,
                            "scope_id": x.scope_id,
                            "summary": x.summary,
                            "full_text": x.full_text,
                            "structured": x.structured,
                            "priority": x.priority,
                            "ttl_turns": x.ttl_turns,
                        }
                        for x in ttl
                    ]
                )

            if gm_out.time_passed_minutes:
                camp.current_datetime = advance_time(
                    camp.current_datetime, gm_out.time_passed_minutes
                )

            payload["gm_thoughts"] = {
                "introspection": gm_out.introspection,
                "pacing": gm_out.pacing,
                "plan": gm_out.plan,
                "world_facts": gm_out.world_facts,
                "scene_focus": gm_out.scene_focus,
            }
            narration = self.llm.narrate(payload=payload)

            ev = Event(
                campaign_id=camp.id,
                actor_id=actor.id,
                campaign_timestamp=camp.current_datetime,
                mode=camp.mode,
                action_text=text,
                intent=intent.model_dump(),
                check={},
                narration=narration.narration,
                result_data={
                    "gm_thoughts": payload["gm_thoughts"],
                    "world_update_notes": world_out.notes,
                },
            )

            db.add(ev)
            camp.turn_count += 1

            world_tick(db, camp.id, 0)

            TURN_COUNTER.labels(result="ok").inc()

            return {
                "status": "ok",
                "phase": "narrative",
                "campaign_id": camp.id,
                "actor_id": actor.id,
                "mode": camp.mode,
                "campaign_time": camp.current_datetime.isoformat(),
                "narration": narration.narration,
            }

        except OllamaError as e:
            TURN_COUNTER.labels(result="llm_error").inc()
            log.exception("ollama_error", error=str(e))
            raise

        except Exception as e:
            TURN_COUNTER.labels(result="error").inc()
            log.exception("turn_error", error=str(e))
            raise

        finally:
            PIPELINE_SECONDS.observe(time.perf_counter() - t0)
    
    def resolve_roll(self, *, db: Session, pending_roll_id: str, d20: int) -> dict[str, Any]:
        pr = db.execute(
            select(PendingRoll).where(PendingRoll.id == pending_roll_id)
        ).scalar_one_or_none()

        if not pr:
            return {"status": "error", "error": "pending_roll_not_found"}

        if pr.resolved:
            return {"status": "error", "error": "pending_roll_already_resolved"}

        actor = db.execute(select(Actor).where(Actor.id == pr.actor_id)).scalar_one()
        camp = db.execute(select(Campaign).where(Campaign.id == pr.campaign_id)).scalar_one()

        # ---- Resolve roll ----

        if pr.roll_type == "skill_check":
            dc = int(pr.dc or 15)
            total = int(d20) + int(pr.modifier)
            outcome = "success" if total >= dc else "fail"

            check_result = {
                "roll_type": "skill_check",
                "skill": pr.skill,
                "dc": dc,
                "d20": int(d20),
                "modifier": int(pr.modifier),
                "total": total,
                "outcome": outcome,
            }

        else:
            total = int(d20)
            outcome = "ok"

            check_result = {
                "roll_type": "initiative",
                "d20": int(d20),
                "total": total,
                "outcome": outcome,
            }

        pr.d20 = int(d20)
        pr.total = total
        pr.outcome = outcome
        pr.resolved = True
        pr.resolved_at = datetime.utcnow()

        db.flush()

        # ---- Director + optional world update + narration ----

        mech = encumbrance_snapshot(db, actor.id)
        scene = self._get_current_scene(db, camp.id)

        sel = {
            "world_nodes": list(
                dict.fromkeys([x for x in ([scene.current_node_id] + list(scene.location_ids or [])) if x])
            ),
            "actors": list(dict.fromkeys(list(scene.npc_ids or []))),
            "context_blocks": [],
            "lore_pages": [],
            "threads": [],
            "item_defs": [],
            "spell_defs": [],
        }
        fetched = fetch_selected(db, sel)
        transcript_text = build_transcript(db, campaign_id=camp.id)

        payload = {
            "campaign_info": {
                "id": camp.id,
                "name": camp.name,
                "mode": camp.mode,
                "current_datetime": camp.current_datetime.isoformat(),
            },
            "mechanics_snapshot": mech,
            "context_blocks_text": "",
            "scene_text": render_current_scene(scene=scene, fetched=fetched),
            "transcript_text": transcript_text,
            "player_text": pr.action_text,
            "check_result": check_result,
        }

        gm_out = self.llm.gm_plan(
            payload={
                "campaign": payload["campaign_info"],
                "player": {"id": actor.id, "name": actor.name},
                "mode": camp.mode,
                "player_text": pr.action_text,
                "check_result": check_result,
                "mechanics_snapshot": mech,
                "scene": {
                    "id": scene.id,
                    "title": scene.title,
                    "summary": scene.summary,
                    "current_node_id": scene.current_node_id,
                    "npc_ids": scene.npc_ids,
                    "location_ids": scene.location_ids,
                },
                "transcript": transcript_text,
                "constraints": {"max_ops": 0},
            }
        )

        world_out = self.llm.world_update(
            payload={
                "campaign": payload["campaign_info"],
                "mode": camp.mode,
                "player_text": pr.action_text,
                "intent": pr.intent,
                "check_result": check_result,
                "gm_thoughts": gm_out.model_dump(),
                "fetched": fetched,
                "constraints": {"max_ops": 4},
            }
        )
        if world_out.ops:
            apply_ops(db, campaign_id=camp.id, ops=[o.model_dump() for o in world_out.ops])
            db.flush()

        # Optional lore retrieval requested by director.
        if gm_out.retrieval_queries:
            for q in gm_out.retrieval_queries[:3]:
                hits = retrieve_lore_chunks(db, llm=self.llm, campaign_id=camp.id, query=q)
                for h in hits[:3]:
                    db.add(
                        ContextBlock(
                            campaign_id=camp.id,
                            type="lore_clip",
                            title=h.get("title") or "Lore",
                            scope_type="global",
                            visibility="player",
                            hardness="soft",
                            summary=(h.get("chunk_text") or "")[:400],
                            full_text=h.get("chunk_text"),
                            structured={"retrieved_for": q, "doc_type": h.get("doc_type")},
                            priority=0.55,
                            ttl_turns=int(settings.CONTEXT_BLOCK_TTL_DEFAULT_TURNS),
                            is_active=True,
                        )
                    )
            db.flush()

        ttl = (
            db.execute(
                select(ContextBlock)
                .where(ContextBlock.campaign_id == camp.id, ContextBlock.is_active == True)
                .where(ContextBlock.ttl_turns.is_not(None))
                .order_by(ContextBlock.priority.desc())
                .limit(12)
            )
            .scalars()
            .all()
        )
        if ttl:
            payload["context_blocks_text"] = render_context_blocks(
                [
                    {
                        "id": x.id,
                        "type": x.type,
                        "title": x.title,
                        "scope_type": x.scope_type,
                        "scope_id": x.scope_id,
                        "summary": x.summary,
                        "full_text": x.full_text,
                        "structured": x.structured,
                        "priority": x.priority,
                        "ttl_turns": x.ttl_turns,
                    }
                    for x in ttl
                ]
            )

        if gm_out.time_passed_minutes:
            camp.current_datetime = advance_time(camp.current_datetime, gm_out.time_passed_minutes)

        payload["gm_thoughts"] = {
            "introspection": gm_out.introspection,
            "pacing": gm_out.pacing,
            "plan": gm_out.plan,
            "world_facts": gm_out.world_facts,
            "scene_focus": gm_out.scene_focus,
        }

        narration = self.llm.narrate(payload=payload)

        # ---- Event ----

        ev = Event(
            campaign_id=camp.id,
            actor_id=actor.id,
            campaign_timestamp=camp.current_datetime,
            mode=camp.mode,
            action_text=pr.action_text,
            intent=pr.intent,
            check=check_result,
            narration=narration.narration,
            result_data={"gm_thoughts": payload["gm_thoughts"], "world_update_notes": world_out.notes},
        )

        db.add(ev)
        camp.turn_count += 1

        return {
            "status": "ok",
            "phase": "narrative",
            "campaign_id": camp.id,
            "actor_id": actor.id,
            "mode": camp.mode,
            "campaign_time": camp.current_datetime.isoformat(),
            "narration": narration.narration,
            "check_result": check_result,
            "gm_thoughts": payload["gm_thoughts"],
        }