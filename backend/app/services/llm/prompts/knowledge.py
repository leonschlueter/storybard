import json

def build_knowledge_prompt(*, player_text: str, mode: str, catalogs: dict, max_total: int = 18) -> tuple[str, str]:
    system = (
        "You are the KNOWLEDGE SELECTOR. "
        "You only choose IDs from the provided catalogs that are needed for the next planning/narration step. "
        "You do not narrate."
    )

    user = f"""MODE: {mode}

PLAYER MESSAGE:
{player_text}

CATALOGS (choose IDs only; max total {max_total}):
{json.dumps(catalogs, ensure_ascii=False)}

Select IDs that are relevant:
- world_nodes, actors, lore_pages, context_blocks, threads, item_defs, spell_defs
Also provide a short 'why' list explaining your selection.
"""
    return system, user
