from __future__ import annotations

import json

def build_location_detail_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the LOCATION WRITER for a tabletop RPG. "
        "Given a location name and minimal campaign context, you produce a rich, grounded location writeup "
        "that fits the campaign tone and tags. "
        "Do not create new factions or world history unless it is consistent with the provided lore/context. "
        "Return structured JSON ONLY that matches the output schema."
    )

    user = f"""# Location Detail Request

## Input
```json
{json.dumps(payload, ensure_ascii=False)}
```

## Requirements
- Be *verbose*: long_description should be 300-800 words.
- Keep short_description <= 240 chars.
- Provide coordinates x/y if missing: use a loose regional map scale (0..100), consistent across locations.
- Add 3-8 tags.
    Do NOT create new locations.
    Nearby locations are computed by the engine.
    Return empty nearby list.
"""

    return system, user
