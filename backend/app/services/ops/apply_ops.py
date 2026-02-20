from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.world import WorldNode
from app.models.actor import Actor
from app.models.actor_profile import ActorProfile
from app.models.lore import LorePage
from app.models.context import ContextBlock
from app.models.thread import StoryThread
from app.models.item_def import ItemDef
from app.models.spell_def import SpellDef
from app.models.inventory import InventoryItem
from app.models.actor_spell import ActorSpell

from app.services.ops.validators import validate_item_effect, validate_spell_effect

def apply_ops(db: Session, *, campaign_id: str, ops: list[dict]) -> dict:
    created = {"world_nodes": [], "actors": [], "lore_pages": [], "context_blocks": [], "threads": [], "item_defs": [], "spell_defs": []}

    for op in ops:
        op_type = op.get("op")
        data = op.get("data") or {}

        if op_type == "create_world_node":
            n = WorldNode(
                campaign_id=campaign_id,
                name=data["name"],
                description=data.get("description"),
                x=data.get("x"),
                y=data.get("y"),
                tags=",".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else "",
            )
            db.add(n)
            db.flush()
            created["world_nodes"].append(n.id)

        elif op_type == "create_actor":
            a = Actor(
                campaign_id=campaign_id,
                name=data["name"],
                kind=data.get("kind", "npc"),
                bio=data.get("bio"),
                current_node_id=data.get("current_node_id"),
            )
            db.add(a)
            db.flush()

            prof = data.get("profile") or {}
            if prof:
                p = ActorProfile(
                    actor_id=a.id,
                    pronouns=prof.get("pronouns"),
                    voice=prof.get("voice"),
                    faction=prof.get("faction"),
                    appearance=prof.get("appearance"),
                    personality=prof.get("personality"),
                    mannerisms=prof.get("mannerisms"),
                    backstory=prof.get("backstory"),
                    goals=prof.get("goals"),
                    secrets=prof.get("secrets"),
                    extra=prof.get("extra", {}),
                )
                db.add(p)

            created["actors"].append(a.id)

        elif op_type == "move_actor":
            a = db.execute(select(Actor).where(Actor.id == data["actor_id"])).scalar_one_or_none()
            if a and a.campaign_id == campaign_id:
                a.current_node_id = data.get("to_node_id")

        elif op_type == "create_lore_page":
            p = LorePage(
                campaign_id=campaign_id,
                title=data["title"],
                summary=data.get("summary"),
                content=data.get("content"),
                tags=data.get("tags", []),
            )
            db.add(p)
            db.flush()
            created["lore_pages"].append(p.id)

        elif op_type == "create_context_block":
            ttl = data.get("ttl_turns")
            if ttl is None and data.get("type") not in ("instruction", "campaign_summary"):
                ttl = 5
            b = ContextBlock(
                campaign_id=campaign_id,
                type=data["type"],
                title=data["title"],
                scope_type=data.get("scope_type", "global"),
                scope_id=data.get("scope_id"),
                visibility=data.get("visibility", "player"),
                hardness=data.get("hardness", "soft"),
                summary=data.get("summary",""),
                full_text=data.get("full_text"),
                structured=data.get("structured", {}),
                priority=float(data.get("priority", 0.5)),
                ttl_turns=ttl,
                is_active=bool(data.get("is_active", True)),
            )
            db.add(b)
            db.flush()
            created["context_blocks"].append(b.id)

        elif op_type == "update_context_block":
            b = db.execute(select(ContextBlock).where(ContextBlock.id == data["id"])).scalar_one_or_none()
            if b and b.campaign_id == campaign_id:
                # compatibility: some older prompts used `text` instead of `summary`
                if "text" in data and data.get("summary") is None:
                    data["summary"] = data.get("text")
                for k in ["title","summary","full_text","structured","priority","ttl_turns","is_active","visibility","hardness","scope_type","scope_id","type"]:
                    if k in data and data[k] is not None:
                        setattr(b, k, data[k])

        elif op_type == "create_story_thread":
            t = StoryThread(
                campaign_id=campaign_id,
                title=data["title"],
                summary=data.get("summary",""),
                status=data.get("status","active"),
                priority=float(data.get("priority", 0.5)),
                state=data.get("state", {}),
                last_updated_at=datetime.utcnow(),
            )
            db.add(t)
            db.flush()
            created["threads"].append(t.id)

        elif op_type == "update_story_thread":
            t = db.execute(select(StoryThread).where(StoryThread.id == data["id"])).scalar_one_or_none()
            if t and t.campaign_id == campaign_id:
                if "title" in data and data["title"] is not None:
                    t.title = data["title"]
                if "summary" in data and data["summary"] is not None:
                    t.summary = data["summary"]
                if "status" in data and data["status"] is not None:
                    t.status = data["status"]
                if "priority" in data and data["priority"] is not None:
                    t.priority = float(data["priority"])
                if "state" in data and data["state"] is not None:
                    t.state = data["state"]
                t.last_updated_at = datetime.utcnow()

        elif op_type == "create_item_def":
            effect = data.get("effect", {})
            validate_item_effect(effect)
            it = ItemDef(
                campaign_id=campaign_id,
                base_type=data.get("base_type","generic"),
                name=data["name"],
                weight=float(data.get("weight", 0.0)),
                rarity=data.get("rarity","common"),
                effect=effect,
                display_name=data.get("display_name"),
                display_description=data.get("display_description"),
                visual_tags=data.get("visual_tags", []),
            )
            db.add(it)
            db.flush()
            created["item_defs"].append(it.id)

        elif op_type == "create_spell_def":
            lvl = int(data.get("level", 0))
            effect = data.get("effect", {})
            validate_spell_effect(effect, lvl)
            sp = SpellDef(
                campaign_id=campaign_id,
                name=data["name"],
                level=lvl,
                school=data.get("school","universal"),
                range=data.get("range","self"),
                duration=data.get("duration","instant"),
                components=data.get("components","V,S"),
                effect=effect,
                display_name=data.get("display_name"),
                display_description=data.get("display_description"),
                visual_tags=data.get("visual_tags", []),
            )
            db.add(sp)
            db.flush()
            created["spell_defs"].append(sp.id)

        elif op_type == "grant_item":
            inv = InventoryItem(
                actor_id=data["actor_id"],
                item_def_id=data["item_def_id"],
                quantity=int(data.get("quantity", 1)),
                equipped=bool(data.get("equipped", False)),
            )
            db.add(inv)

        elif op_type == "grant_spell":
            asp = ActorSpell(
                actor_id=data["actor_id"],
                spell_def_id=data["spell_def_id"],
                prepared=bool(data.get("prepared", True)),
            )
            db.add(asp)

        # unknown ops are ignored in dev build

    return created
