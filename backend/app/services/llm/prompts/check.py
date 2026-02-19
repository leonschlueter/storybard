def build_check_prompt(*, player_text: str, mode: str, mechanics_snapshot: dict, location_name: str | None) -> tuple[str, str]:
    system = (
        "You are the CHECK ADVISOR for a tabletop RPG engine. "
        "You decide whether the player's action should require a dice roll (skill check or initiative request). "
        "If a skill check is required, you propose an explicit numeric DC and a short reason. "
        "You do NOT resolve the roll and you do NOT narrate."
    )

    user = f"""MODE: {mode}
LOCATION: {location_name or "Unknown"}

MECHANICS SNAPSHOT (engine computed):
{mechanics_snapshot}

PLAYER MESSAGE:
{player_text}

Rules:
- If the action is mundane or guaranteed, phase=narrative.
- If uncertain, phase=skill_check_required and roll_type=skill_check.
- If likely to start combat, phase=initiative_required and roll_type=initiative.
- When proposing a DC:
  - include dc (integer 5..30) and dc_reason (1 sentence).
  - include difficulty band (trivial/easy/medium/hard/very_hard).
- Propose time_passed_minutes (0..120) with time_reason.
"""
    return system, user
