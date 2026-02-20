def build_check_prompt(*, player_text: str, mode: str, mechanics_snapshot: dict, location_name: str | None) -> tuple[str, str]:
    system = (
        "You are the CHECK ADVISOR for a tabletop RPG engine. "
        "You decide whether the player's action should require a dice roll (skill check or initiative request). "
        "If a skill check is required, you propose an explicit numeric DC and a short reason. "
        "You do NOT resolve the roll and you do NOT narrate."
    )

    user = f"""# Check Advisor

## Context
- Mode: **{mode}**
- Location: **{location_name or "Unknown"}**

## Mechanics Snapshot
```json
{mechanics_snapshot}
```

## Player Message
{player_text}

## Rules (Important)
- Default is **phase=narrative**.
- Only require a roll if the outcome is **meaningfully uncertain** *and* failure would change what happens.
- Talking, asking questions, looking around, and normal movement are usually **no roll**.
- Social rolls only when the NPC would plausibly refuse, lie, or be swayed.
- If combat is about to begin, use **initiative_required**.
- If you require a skill check:
  - set phase=skill_check_required, roll_type=skill_check
  - choose a skill and DC 5..30 and 1-sentence dc_reason
- Propose time_passed_minutes (0..120) with time_reason.
"""
    return system, user
