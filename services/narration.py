from database.narrative import LLMCallLog
from sqlalchemy.orm import Session
from database.history.history import GameHistory
from datetime import datetime

from openai import OpenAI

def build_prompt(db: Session, player_input: str) -> str:
    # Get last 10 messages (player and GM)
    history = (
        db.query(GameHistory)
        .order_by(GameHistory.timestamp.desc())
        .limit(10)
        .all()
    )[::-1]  # reverse to chronological order
    history = reversed(history)  # chronological order

    chat = ""
    for entry in history:
        if entry.player_input:
            chat += f"\nPlayer: {entry.player_input}"
        if entry.narration:
            chat += f"\nNarrator: {entry.narration}"

    chat += f"Player: {player_input}\n"

    return f"""

Previous conversation:
{chat}

Now continue as the GM.
"""

def call_openai_structured(client: OpenAI, system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.85,
            max_tokens=300
        )
        text = response.choices[0].message.content.strip()
        return text, response
    except Exception as e:
        return f"(LLM ERROR) {str(e)}", {}