def build_intent_prompt(*, player_text: str, mode: str) -> tuple[str, str]:
    system = (
        "You are the INTENT PARSER for a tabletop RPG engine. "
        "Your job is to classify the player's message into a primitive action and identify any explicit mode request. "
        "You do not narrate, and you do not decide outcomes."
    )

    user = f"""MODE: {mode}

PLAYER MESSAGE:
{player_text}

Guidelines:
- primitive should be one of: move, speak, interact, inspect, use_item, cast_spell, rest, wait, downtime_action, attack, unknown
- If the message explicitly requests a mode, set requested_mode to explore/downtime/battle.
- target should be short (a person/place/object).
- notes can include brief clarifications.
"""
    return system, user
