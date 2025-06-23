from sqlalchemy.orm import Session
from datetime import datetime
from database.characters.player import Player
from database.characters.npc import NPC
from database.characters.faction import Faction
from database.characters.character import Character
from database.locations.city_data import CityData
from database.locations.kingdom_data import KingdomData
from database.locations.region_data import RegionData
from database.locations.location import Location
from database.locations.world_data import WorldData
from database.items.item import Item
from database.items.weapon import Weapon
from database.items.armor import Armor
from database.items.spell import Spell
from database.narrative.scene import NarrativeScene
from database.narrative.arc import NarrativeArc
from database.narrative.gm_intent import GMIntent
from database.narrative.scene_link import SceneLink
from database.narrative.hook import Hook


# ------------------------------
# 🔁 Generic Add or Update
# ------------------------------
def add_or_update(session: Session, model_class, data: dict, identifier: str = "id"):
    obj = None
    if identifier in data:
        obj = session.query(model_class).filter(getattr(model_class, identifier) == data[identifier]).first()
    if obj:
        for key, value in data.items():
            setattr(obj, key, value)
    else:
        obj = model_class(**data)
        session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj

# ------------------------------
# 🌍 WorldData & Locations
# ------------------------------
def add_worlddata(session: Session, **kwargs): return add_or_update(session, WorldData, kwargs)
def add_kingdom(session: Session, **kwargs): return add_or_update(session, KingdomData, kwargs)
def add_region(session: Session, **kwargs): return add_or_update(session, RegionData, kwargs)
def add_city(session: Session, **kwargs): return add_or_update(session, CityData, kwargs)
def add_location(session: Session, **kwargs): return add_or_update(session, Location, kwargs)

# ------------------------------
# 👤 Characters & Factions
# ------------------------------
def add_player(session: Session, **kwargs): return add_or_update(session, Player, kwargs)
def add_npc(session: Session, **kwargs): return add_or_update(session, NPC, kwargs)
def add_faction(session: Session, **kwargs): return add_or_update(session, Faction, kwargs)
def add_character(session: Session, **kwargs): return add_or_update(session, Character, kwargs)

def update_player_location(session: Session, player_id: int, new_location_id: int):
    player = session.query(Player).filter_by(id=player_id).first()
    if player:
        player.location_id = new_location_id
        session.commit()
    return player

# ------------------------------
# 🧠 Threads & Story
# ------------------------------

def add_arc(session: Session, **kwargs): return add_or_update(session, NarrativeArc, kwargs)
def add_scene(session: Session, **kwargs): return add_or_update(session, NarrativeScene, kwargs)
def add_scene_link(session: Session, **kwargs): return add_or_update(session, SceneLink, kwargs)
def add_gm_intent(session: Session, **kwargs): return add_or_update(session, GMIntent, kwargs)

# ------------------------------
# 📌 Hooks
# ------------------------------
def add_hook(session: Session, **kwargs): return add_or_update(session, Hook, kwargs)

# ------------------------------
# ⚔️ Inventory System
# ------------------------------
def add_item(session: Session, **kwargs): return add_or_update(session, Item, kwargs)
def add_weapon(session: Session, **kwargs): return add_or_update(session, Weapon, kwargs)
def add_armor(session: Session, **kwargs): return add_or_update(session, Armor, kwargs)
def add_spell(session: Session, **kwargs): return add_or_update(session, Spell, kwargs)

# ------------------------------
# 🧭 Optional Getters
# ------------------------------
def get_player(session: Session, player_id: int): return session.query(Player).filter_by(id=player_id).first()
def get_location(session: Session, location_id: int): return session.query(Location).filter_by(id=location_id).first()
def get_scene(session: Session, scene_id: int): return session.query(NarrativeScene).filter_by(id=scene_id).first()
def get_arc(session: Session, arc_id: int): return session.query(NarrativeArc).filter_by(id=arc_id).first()
def get_intents_for_target(session: Session, target_type: str, target_id: int):
    return session.query(GMIntent).filter_by(target_type=target_type, target_id=target_id, is_active=False, is_consumed=False).all()

# ------------------------------
# 🧩 Batch Apply Helpers
# ------------------------------
def apply_worlddata_update(session: Session, update):
    for char in update.characters: add_npc(session, **char.dict())
    for item in update.items: add_item(session, **item.dict())
    for loc in update.locations: add_location(session, **loc.dict())
    for hook in update.hooks: add_hook(session, **hook.dict())

def apply_narrative_update(session: Session, update):
    for scene in update.scenes: add_scene(session, **scene.dict())
    for link in update.scene_links: add_scene_link(session, **link.dict())
    for arc in update.arcs: add_arc(session, **arc.dict())
    for intent in update.gm_intents: add_gm_intent(session, **intent.dict())