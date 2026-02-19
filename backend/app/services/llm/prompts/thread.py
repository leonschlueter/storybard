import json

def build_thread_prompt(*, payload: dict) -> tuple[str, str]:
    system = (
        "You are the STORY THREAD ADVANCER. "
        "You update active story threads based on recent events. "
        "You do NOT narrate. "
        "You output ops to update or create story threads."
    )
    user = f"""PAYLOAD:
{json.dumps(payload, ensure_ascii=False)}

Rules:
- Update existing threads when possible.
- You may create a new thread if the recent events strongly suggest it.
- Keep ops under payload.constraints.max_ops.
"""
    return system, user
