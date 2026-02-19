import json

def build_memory_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the MEMORY REGRESSOR. "
        "You create short-lived memory/context blocks that help maintain continuity, without bloating history. "
        "You do NOT narrate."
    )
    user = f"""PAYLOAD:
{json.dumps(payload, ensure_ascii=False)}

Rules:
- Output ops that create context blocks of type 'memory' with ttl_turns between 3 and 8.
- Memories must be grounded in the provided event/narration.
- Keep ops under payload.constraints.max_ops.
"""
    return system, user
