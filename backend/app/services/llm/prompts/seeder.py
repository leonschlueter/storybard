import json

def build_seeder_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the CAMPAIGN SEEDER for a tabletop RPG engine. "
        "You generate a medium-sized playable starting world: locations, lore, NPCs, and 3+ story threads. "
        "You do NOT write narration; you generate structured seed data."
    )
    user = f"""SEED INPUT:
{json.dumps(payload, ensure_ascii=False)}

Constraints:
- World size: medium (5-10 locations).
- NPCs: 2-5 named NPCs with motivations.
- Lore: 8-14 lore facts involving the world's history, factions, and key locations.
- Threads: 3-5 story threads with clear hooks connecting to locations and NPCs.
- Ensure start_location matches one of world_nodes names.
- Provide start_date_iso as YYYY-MM-DD.
"""
    return system, user
