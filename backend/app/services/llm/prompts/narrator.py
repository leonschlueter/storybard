import json

def build_narrator_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the NARRATOR for a tabletop RPG campaign. "
        "You produce coherent, grounded narration that respects mechanics and world canon provided. "
        "You do NOT invent new canon entities beyond the provided context (unless explicitly allowed in payload). "
        "All context is visible to the player in this dev build."
    )

    user = f"""NARRATION STYLE:
{payload.get("narration_style")}

--- GENERAL CAMPAIGN INFO ---
{json.dumps(payload.get("campaign_info"), ensure_ascii=False)}

--- CAMPAIGN SUMMARY ---
{payload.get("campaign_summary")}

--- ACTIVE THREADS ---
{json.dumps(payload.get("threads"), ensure_ascii=False)}

--- MECHANICS SNAPSHOT (IMPORTANT) ---
{json.dumps(payload.get("mechanics_snapshot"), ensure_ascii=False)}

--- CONTEXT BLOCKS ---
{payload.get("context_blocks_text")}

--- LORE PAGES ---
{payload.get("lore_pages_text")}

--- RECENT HISTORY (last few turns) ---
{payload.get("recent_history_text")}

--- PLAYER MESSAGE ---
{payload.get("player_text")}

--- CHECK RESULT (if any) ---
{json.dumps(payload.get("check_result") or {}, ensure_ascii=False)}

Write 120-220 words unless the situation requires a shorter response.
Return vivid but playable narration. Offer 2-4 actionable options implicitly (not as a list unless appropriate).
"""
    return system, user
