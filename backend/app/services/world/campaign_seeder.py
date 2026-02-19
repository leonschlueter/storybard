from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.campaign import Campaign
from app.models.world import WorldNode
from app.models.actor import Actor
from app.models.character_sheet import CharacterSheet
from app.models.context import ContextBlock
from app.models.thread import StoryThread
from app.models.item_def import ItemDef
from app.models.inventory import InventoryItem
from app.models.spell_def import SpellDef

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
        node = WorldNode(
            campaign_id=camp.id,
            name=wn.name,
            description=wn.description,
            x=wn.x,
            y=wn.y,
            tags=",".join(wn.tags),
        )
        db.add(node)
        db.flush()
        name_to_node[wn.name] = node

        # Visible context block for each location
        db.add(ContextBlock(
            campaign_id=camp.id,
            type="location",
            title=wn.name,
            scope_type="location",
            scope_id=node.id,
            visibility="player",
            hardness="hard",
            summary=wn.description,
            priority=0.7,
            is_active=True
        ))

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

    # NPCs
    for npc in seed.npcs:
        node = name_to_node.get(npc.start_location) or start_node
        a = Actor(
            campaign_id=camp.id,
            name=npc.name,
            kind=ActorKind.npc.value,
            bio=npc.bio,
            current_node_id=node.id,
        )
        db.add(a)
        db.flush()
        db.add(ContextBlock(
            campaign_id=camp.id,
            type="npc",
            title=npc.name,
            scope_type="actor",
            scope_id=a.id,
            visibility="player",
            hardness="soft",
            summary=npc.bio,
            priority=0.6,
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
    return camp, player, start_node
