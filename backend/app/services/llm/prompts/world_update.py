from __future__ import annotations

import json


def build_world_update_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the WORLD BUILDER. "
        "You may propose safe database operations to create/update world entities: "
        "NPCs, locations, lore pages, and context blocks. "
        "Only propose ops that follow from the provided payload. "
        "Prefer updating existing entities over creating new ones. "
        "When creating NPCs/locations, include rich descriptions and all required fields. "
        "Never create overpowered spells/items. "
        "Return ONLY structured ops." 
    )

    user = f"""WORLD UPDATE PAYLOAD (JSON):
{json.dumps(payload, ensure_ascii=False)}

Rules:
- Keep ops under payload.constraints.max_ops.
- For create_context_block: include fields: type, title, summary, scope_type, scope_id (nullable), visibility, hardness, priority.
- For create_actor: include fields: name, kind, bio, current_node_id (nullable).
- For create_actor_profile: include actor_id plus rich fields (appearance, personality, mannerisms, backstory, goals, pronouns, voice, faction, age, species, occupation, alignment, extra).
- For create_memory: include owner_actor_id, subject_actor_id (nullable), title (nullable), text, importance (1..5).
- For create_world_node: include name, description, tags.
- For update_scene: include any subset of title, summary, world_info, nearby_info, npc_ids, location_ids.
"""
    return system, user
