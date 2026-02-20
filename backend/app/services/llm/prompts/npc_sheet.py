from __future__ import annotations

import json

def build_npc_sheet_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the NPC SHEET WRITER for a tabletop RPG. "
        "Given an NPC concept and campaign context, produce a complete NPC sheet. "
        "Be grounded and consistent with the setting. "
        "Return structured JSON ONLY that matches the output schema."
    )

    user = f"""# NPC Sheet Request

## Input
```json
{json.dumps(payload, ensure_ascii=False)}
```

## Requirements
- Be *verbose* in appearance/personality/mannerisms/backstory (each 60-180 words).
- bio should be 1-3 sentences.
- goals: 2-5 concrete goals.
- Provide a lightweight D&D-ish stat block that is mechanically reasonable.
- memories: 0-4 entries that can be stored as NPC memories.
"""

    return system, user
