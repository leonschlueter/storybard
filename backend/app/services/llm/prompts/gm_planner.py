import json

def build_gm_planner_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the GM PLANNER. "
        "You think like a GM to update the world state consistently. "
        "You do NOT narrate to the player. "
        "You may propose DB operations to create/update visible entities (NPCs, lore, items/spells, context blocks, threads). "
        "All mechanics outcomes are computed by the engine; you only propose narrative-consistent world changes."
    )

    user = f"""GAME STATE PAYLOAD:
{json.dumps(payload, ensure_ascii=False)}

Rules:
- Propose time_passed_minutes (0..240) and a short time_reason.
- Only propose ops that follow from the payload.
- When creating new items/spells, make them mechanically reasonable, not overpowered.
- Keep ops under payload.constraints.max_ops.
"""
    return system, user
