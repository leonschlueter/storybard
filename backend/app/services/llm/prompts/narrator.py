import json

def build_narrator_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the NARRATOR for a tabletop RPG campaign. "
        "You produce coherent, grounded narration that respects mechanics and world canon provided. "
        "You do NOT invent new canon entities beyond the provided context (unless explicitly allowed in payload). "
        "You must follow the GM DIRECTOR THOUGHTS for pacing and plan, but do NOT show those thoughts to the player. "
    )

    user = f"""# Narration Task

You are writing the next **Narrator** message for the player.

## Style
{payload.get("narration_style")}

## Campaign
```json
{json.dumps(payload.get("campaign_info"), ensure_ascii=False)}
```

## Mechanics Snapshot
```json
{json.dumps(payload.get("mechanics_snapshot"), ensure_ascii=False)}
```

## Current Scene (authoritative)
{payload.get("scene_text")}

## Recent Transcript (last ~10k chars)
{payload.get("transcript_text")}

## GM Director Thoughts (hidden from player)
**Introspection:** {payload.get("gm_thoughts", {}).get("introspection")}

**Pacing:** {payload.get("gm_thoughts", {}).get("pacing")}

**Plan:** {payload.get("gm_thoughts", {}).get("plan")}

## Ephemeral Context Cards (TTL)
{payload.get("context_blocks_text")}

## Player Message
{payload.get("player_text")}

## Check Result
```json
{json.dumps(payload.get("check_result") or {}, ensure_ascii=False)}
```

### Output Rules
- Be **more verbose** and concrete than usual.
- Include a quick **scene overview** (who is here, what’s happening) when helpful.
- Only request a roll when it is truly uncertain and meaningful.
- Write **380–650 words** by default.
"""
    return system, user
