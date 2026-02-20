from __future__ import annotations

import json


def build_gm_planner_prompt(*, payload: dict) -> tuple[str, str]:
    """Friends & Fables-style "Thoughts" output.

    This output is NOT shown to the player directly. It is fed into narration.
    """

    system = (
        "You are the GM DIRECTOR (Thoughts). "
        "You do NOT narrate to the player. "
        "Your job is to think out loud for the GM UI, producing three sections: "
        "Introspection, Pacing, Plan. "
        "Write full sentences. Be specific to the current scene and the player's last action. "
        "Do not invent mechanics outcomes; the engine handles rules and rolls. "
        "Keep it brief and actionable (2-6 sentences per section)."
    )

    user = f"""# GM Director Thoughts (Not shown to player)

You are producing the **GM UI Thoughts** panel. Your output will be fed into the narrator.

## Game State (JSON)
```json
{json.dumps(payload, ensure_ascii=False)}
```

## Output Rules
- Write **full sentences**.
- Stay grounded in the provided scene and transcript.
- Don’t force rolls. Only recommend uncertainty when it matters.
- Keep each section **2–6 sentences**.

## Return these fields
- `time_passed_minutes` (0..240) and `time_reason`
- `introspection` (what’s really going on / motives / emotions)
- `pacing` (tempo + tension guidance)
- `plan` (beats for the next narrator message + a question to the player)
- `world_facts` (0–6 bullet reminders)
- `scene_focus` (0–6 tags/keywords)
- `retrieval_queries` (0–3 optional lore queries; leave empty unless truly needed)
"""
    return system, user
