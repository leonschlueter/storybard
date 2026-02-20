from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.campaign import Campaign
from app.models.world import WorldNode
from app.models.actor import Actor
from app.models.actor_profile import ActorProfile
from app.models.character_sheet import CharacterSheet
from app.models.memory import Memory
from app.models.context import ContextBlock
from app.models.thread import StoryThread
from app.models.item_def import ItemDef
from app.models.inventory import InventoryItem
from app.models.spell_def import SpellDef
from app.models.scene import Scene
from app.models.event import Event
from app.models.campaign_settings import CampaignSettings
from app.models.lore_document import LoreDocument

from app.services.lore.indexer import index_lore_document

from app.services.llm.roles import LLMRoles
from app.utils.enums import ActorKind, CampaignMode

def default_fighter_sheet() -> dict:
    return {
        "ability_scores": {"STR": 16, "DEX": 13, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "proficiencies": {"skills": ["athletics", "perception"], "saves": ["STR", "CON"]},
        "max_hp": 12,
        "current_hp": 12,
        "speed": 30,
        "gold": 10,
        "spell_slots": {},
        "conditions": [],
    }

def seed_campaign(db: Session, llm: LLMRoles, *, name: str, narration_style: str, genre: str, themes: list[str], magic_level: str, constraints: list[str]) -> tuple[Campaign, Actor, WorldNode]:
    # Create campaign first (calendar data will be updated from LLM output)
    camp = Campaign(
        name=name,
        mode=CampaignMode.explore.value,
        narration_style=narration_style,
        tone_profile={"genre": genre, "magic_level": magic_level},
        reskin_profile={},
        setting_tags=themes,
    )
    db.add(camp)
    db.flush()

    # Default campaign settings (editable in UI)
    db.add(
        CampaignSettings(
            campaign_id=camp.id,
            ruleset="dnd5e",
            tech_level="fantasy_medieval",
            magic_level=magic_level,
        )
    )

    payload = {
        "campaign_name": name,
        "narration_style": narration_style,
        "genre": genre,
        "themes": themes,
        "magic_level": magic_level,
        "constraints": constraints,
    }
    seed = llm.seed_campaign(payload=payload)

    # Apply calendar
    try:
        start_date = datetime.fromisoformat(seed.start_date_iso + "T09:00:00")
    except Exception:
        start_date = datetime.utcnow()

    camp.calendar_name = seed.calendar_name
    camp.start_datetime = start_date
    camp.current_datetime = start_date

    # World nodes
    name_to_node: dict[str, WorldNode] = {}
    for wn in seed.world_nodes:
        # Separate per-location generation: enrich each location with a verbose writeup.
        try:
            loc = llm.write_location(
                payload={
                    "campaign": {
                        "name": camp.name,
                        "genre": "fantasy",
                        "themes": (camp.setting_tags or []),
                        "tone": camp.tone_profile,
                    },
                    "location": {
                        "name": wn.name,
                        "short_description": wn.description,
                        "x": wn.x,
                        "y": wn.y,
                        "tags": wn.tags,
                    },
                    "existing_locations": [n.name for n in name_to_node.values()],
                }
            )
        except Exception:
            loc = None

        node = WorldNode(
            campaign_id=camp.id,
            name=wn.name,
            description=(loc.short_description if loc else wn.description),
            description_long=(loc.long_description if loc else wn.description),
            x=(loc.x if loc and loc.x is not None else wn.x),
            y=(loc.y if loc and loc.y is not None else wn.y),
            tags=",".join((loc.tags if loc else wn.tags) or []),
        )
        db.add(node)
        db.flush()
        name_to_node[wn.name] = node

        # Visible context block for each location
        db.add(
            ContextBlock(
                campaign_id=camp.id,
                type="location",
                title=wn.name,
                scope_type="location",
                scope_id=node.id,
                visibility="player",
                hardness="hard",
                summary=(loc.short_description if loc else wn.description),
                full_text=(loc.long_description if loc else wn.description),
                structured={"tags": (loc.tags if loc else wn.tags) or []},
                priority=0.7,
                ttl_turns=None,  # world canon
                is_active=True,
            )
        )

    start_node = name_to_node.get(seed.start_location) or next(iter(name_to_node.values()))

    # Lore pages + context blocks
    for lp in seed.lore:
        db.add(ContextBlock(
            campaign_id=camp.id,
            type="lore_hint",
            title=lp.title,
            scope_type="global",
            visibility="player",
            hardness="soft",
            summary=lp.content[:280],
            full_text=lp.content,
            structured={"tags": lp.tags},
            priority=0.55,
            is_active=True
        ))

    # Long-form lore document (world primer)
    primer_md = "# Campaign Primer\n\n" + (seed.campaign_summary or "") + "\n\n" + "# Lore Facts\n\n" + "\n".join(
        [f"- **{lp.title}**: {lp.content}" for lp in seed.lore]
    )
    primer = LoreDocument(
        campaign_id=camp.id,
        title="World Primer",
        doc_type="world",
        status="canon",
        content_markdown=primer_md,
        tags=[genre] + themes,
        source="seed",
    )
    db.add(primer)
    db.flush()
    index_lore_document(db, llm=llm, doc=primer)

    # NPCs
    created_npc_ids: list[str] = []
    for npc in seed.npcs:
        node = name_to_node.get(npc.start_location) or start_node

        # Separate per-NPC generation: produce a full NPC sheet.
        try:
            sheet = llm.write_npc(
                payload={
                    "campaign": {
                        "name": camp.name,
                        "themes": (camp.setting_tags or []),
                        "tone": camp.tone_profile,
                    },
                    "location": {"id": node.id, "name": node.name},
                    "npc_concept": {"name": npc.name, "bio": npc.bio},
                }
            )
        except Exception:
            sheet = None

        a = Actor(
            campaign_id=camp.id,
            name=(sheet.name if sheet else npc.name),
            kind=ActorKind.npc.value,
            bio=(sheet.bio if sheet else npc.bio),
            current_node_id=node.id,
        )
        db.add(a)
        db.flush()
        created_npc_ids.append(a.id)
        db.add(
            ActorProfile(
                actor_id=a.id,
                appearance=(sheet.appearance if sheet else None),
                personality=(sheet.personality if sheet else None),
                mannerisms=(sheet.mannerisms if sheet else None),
                backstory=(sheet.backstory if sheet else None),
                goals=(sheet.goals if sheet else None),
                pronouns=(sheet.pronouns if sheet else None),
                voice=(None),
                faction=(sheet.faction if sheet else None),
                extra={
                    "seeded": True,
                    "species": (sheet.species if sheet else None),
                    "age": (sheet.age if sheet else None),
                    "occupation": (sheet.occupation if sheet else None),
                    "alignment": (sheet.alignment if sheet else None),
                    "class": (sheet.class_name if sheet else None),
                },
            )
        )

        if sheet:
            db.add(
                CharacterSheet(
                    actor_id=a.id,
                    level=int(sheet.level),

                    max_hp=int(sheet.max_hp),
                    current_hp=int(sheet.max_hp),

                    armor_class=int(sheet.armor_class),
                    speed=int(sheet.speed),

                    ability_scores=sheet.abilities,      # map correctly
                    proficiencies={
                        "skills": sheet.skills
                    }
                )
            )

            for m in sheet.memories[:4]:
                db.add(
                    Memory(
                        campaign_id=camp.id,
                        owner_actor_id=a.id,
                        subject_actor_id=None,
                        title=str(m.get("title") or "Memory"),
                        text=str(m.get("text") or ""),
                        importance=int(m.get("importance") or 3),
                    )
                )

        db.add(ContextBlock(
            campaign_id=camp.id,
            type="npc",
            title=(sheet.name if sheet else npc.name),
            scope_type="actor",
            scope_id=a.id,
            visibility="player",
            hardness="soft",
            summary=(sheet.bio if sheet else npc.bio),
            full_text=(sheet.backstory if sheet else None),
            priority=0.6,
            ttl_turns=None,
            is_active=True
        ))

    # Threads
    for th in seed.threads:
        t = StoryThread(
            campaign_id=camp.id,
            title=th.title,
            summary=th.summary,
            status="active",
            priority=float(th.priority),
            state=th.initial_state,
            last_updated_at=datetime.utcnow(),
        )
        db.add(t)
        db.flush()
        db.add(ContextBlock(
            campaign_id=camp.id,
            type="thread",
            title=th.title,
            scope_type="thread",
            scope_id=t.id,
            visibility="player",
            hardness="soft",
            summary=th.summary,
            priority=min(0.9, 0.6 + float(th.priority)/4.0),
            is_active=True
        ))

    # Starter items/spells definitions
    item_defs: list[ItemDef] = []
    for it in seed.starter_items:
        idef = ItemDef(
            campaign_id=camp.id,
            base_type=it.base_type,
            name=it.name,
            weight=float(it.weight),
            rarity=it.rarity,
            effect=it.effect,
            display_description=it.display_description,
            visual_tags=it.visual_tags,
        )
        db.add(idef)
        db.flush()
        item_defs.append(idef)

    spell_defs: list[SpellDef] = []
    for sp in seed.starter_spells:
        sdef = SpellDef(
            campaign_id=camp.id,
            name=sp.name,
            level=int(sp.level),
            school=sp.school,
            range=sp.range,
            duration=sp.duration,
            components=sp.components,
            effect=sp.effect,
            display_description=sp.display_description,
            visual_tags=sp.visual_tags,
        )
        db.add(sdef)
        db.flush()
        spell_defs.append(sdef)

    # Player
    player = Actor(
        campaign_id=camp.id,
        name="Arin",
        kind=ActorKind.player.value,
        bio="A fresh adventurer in a new land.",
        current_node_id=start_node.id,
    )
    db.add(player)
    db.flush()

    db.add(ActorProfile(actor_id=player.id, pronouns="they/them", extra={"seeded": True}))

    sheet_data = default_fighter_sheet()
    db.add(CharacterSheet(
        actor_id=player.id,
        level=1,
        class_name="Fighter",
        race="Human",
        background="Wanderer",
        ability_scores=sheet_data["ability_scores"],
        proficiencies=sheet_data["proficiencies"],
        max_hp=sheet_data["max_hp"],
        current_hp=sheet_data["current_hp"],
        speed=sheet_data["speed"],
        gold=sheet_data["gold"],
        spell_slots=sheet_data["spell_slots"],
        conditions=sheet_data["conditions"],
    ))

    # Give player a couple starter items if any exist, else a basic pack
    if not item_defs:
        basic = [
            ("Backpack", 5.0, {"type":"container"}),
            ("Rations (1 day)", 2.0, {"type":"consumable"}),
            ("Torch", 1.0, {"type":"utility"}),
            ("Waterskin", 5.0, {"type":"utility"}),
        ]
        for nm, wt, ef in basic:
            idef = ItemDef(campaign_id=camp.id, name=nm, base_type="gear", weight=wt, rarity="common", effect=ef)
            db.add(idef)
            db.flush()
            item_defs.append(idef)

    for idef in item_defs[:3]:
        db.add(InventoryItem(actor_id=player.id, item_def_id=idef.id, quantity=1, equipped=False))

    # Plot summary (for UI) + campaign summary (engine)
    db.add(ContextBlock(
        campaign_id=camp.id,
        type="plot_summary",
        title="Plot Summary",
        scope_type="global",
        visibility="player",
        hardness="hard",
        summary=seed.campaign_summary,
        priority=0.95,
        is_active=True,
        structured={"kind": "plot"}
    ))

    # Campaign summary block seed
    db.add(ContextBlock(
        campaign_id=camp.id,
        type="campaign_summary",
        title="Campaign Summary",
        scope_type="global",
        visibility="player",
        hardness="hard",
        summary=seed.campaign_summary,
        priority=1.0,
        is_active=True,
        structured={"last_summarized_turn": 0}
    ))

    db.flush()

    # Current scene (prototype) - defaults to start location and a few nearby NPCs
    scene = Scene(
            campaign_id=camp.id,
            title="Current Scene",
            summary=start_node.description,
            current_node_id=start_node.id,
            npc_ids=created_npc_ids[:2],
            location_ids=[start_node.id],
            world_info=f"This campaign takes place in a {genre} world. Currencies, laws, and customs may vary.",
            nearby_info="",
            is_current=True,
        )
    db.add(scene)
    db.flush()

    # Opening narration: narrator sets the scene (no player input yet)
    try:
        gm_out = llm.gm_plan(
            payload={
                "campaign": {
                    "id": camp.id,
                    "name": camp.name,
                    "mode": camp.mode,
                    "current_datetime": camp.current_datetime.isoformat(),
                },
                "player": {"id": player.id, "name": player.name},
                "location": {"id": start_node.id, "name": start_node.name},
                "mode": camp.mode,
                "player_text": "(scene begins)",
                "intent": {"primitive": "none", "target": None, "requested_mode": None, "notes": []},
                "mechanics_snapshot": {"encumbered": False, "carried_weight": 0.0, "max_weight": 0, "speed_base": 30, "speed_effective": 30},
                "threads": [],
                "fetched": {},
                "constraints": {"max_ops": 0},
            }
        )
    except Exception:
        gm_out = None

    try:
        narration = llm.narrate(
            payload={
                "campaign_info": {
                    "id": camp.id,
                    "name": camp.name,
                    "mode": camp.mode,
                    "current_datetime": camp.current_datetime.isoformat(),
                },
                "campaign_summary": seed.campaign_summary,
                "threads": [],
                "mechanics_snapshot": {"encumbered": False, "carried_weight": 0.0, "max_weight": 0, "speed_base": 30, "speed_effective": 30},
                "current_scene": {
                    "title": scene.title,
                    "summary": scene.summary,
                    "world_info": scene.world_info,
                    "nearby_info": scene.nearby_info,
                },
                "player_text": "(scene begins)",
                "check_result": {},
                "gm_director": (gm_out.gm_director.model_dump() if gm_out and gm_out.gm_director else None),
                "context_blocks_text": "",
                "lore_pages_text": "",
                "recent_history_text": "",
            }
        )
        db.add(
            Event(
                campaign_id=camp.id,
                actor_id=player.id,
                campaign_timestamp=camp.current_datetime,
                mode=camp.mode,
                action_text="(scene begins)",
                intent={},
                check={},
                narration=narration.narration,
                result_data={
                    "gm_director": (gm_out.gm_director.model_dump() if gm_out and gm_out.gm_director else None)
                },
            )
        )
    except Exception:
        pass
    return camp, player, start_node
