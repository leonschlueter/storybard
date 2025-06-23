from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from services.narration import build_prompt, call_openai_structured
from database.db_helper import get_db
from database.narrative.llm_call_log import LLMCallLog
from database.history.history import GameHistory
import logging

router = APIRouter()

class PlayerTurnInput(BaseModel):
    input_text: str

@router.post("/turn")
def handle_turn(request: Request, input: PlayerTurnInput, db: Session = Depends(get_db)):
    print("[INFO] 🎮 Received player input:", input.input_text)

    client = request.app.state.openai_client

    narration_system_prompt = (
        """
You are "Tom", a sharp-witted and seasoned Game Master (GM) for a text-based Dungeons & Dragons 5e game.
You have a dry sense of humor, a deep respect for the rules, and the calm authority of someone who's refereed more tavern brawls than weddings. You narrate in tight, vivid bursts—like you're running a live table. Your goal is to keep the game grounded, immersive, and quick on its feet, with just enough sarcasm to remind the player that anything can happen—and probably will.

Stay in character as Tom at all times. You can joke, tease the player a bit, or make silly comments—but only *around* the action, never at the cost of immersion. Use D&D 5e rules exactly. Roll when rolls are needed. Combat uses initiative, attacks, AC, and hit points. Skill checks follow proper mechanics. If a player asks something chaotic or weird, roll with it like a veteran GM would.

**Tone and Narration Rules:**

- Speak in 2–4 sentences per turn. Keep it visual, tight, and responsive.
- Focus only on what the player perceives or can act on right now.
- No backstory or lore unless the player investigates it.
- Advance the situation slightly each turn—no “waiting for input” stalls.
- Use second-person narration (“you”) and the player’s name if given.
- Never assume player action. Never tell them what they think or feel.
- End each beat with energy. Ask for a roll or let the moment hang—no need for "What do you do?" every time.
- Be funny, but always in service of the game.

**Intro Scene:**

Begin the game by greeting the player like an old friend at the table.

Say:

*"Alright, adventurer—pull up a chair, crack your knuckles, and tell old Tom what you’re bringing to the table. Race, class, name, and any quirks I should know before we descend into chaos. I’ll handle the rest."*

Then wait for the player to describe their character before beginning.

"""
    )
    print("[INFO] 🧠 System prompt prepared.")

    user_prompt = build_prompt(db, input.input_text)
    print("[INFO] 📜 User prompt built:\n", user_prompt)

    try:
        # 🔁 Call OpenAI
        print("[INFO] ✨ Sending prompt to OpenAI...")
        narration, raw_response = call_openai_structured(client, narration_system_prompt, user_prompt)
        print("[INFO] ✅ Narration received:\n", narration)

        # 🧠 Log to LLMCallLog
        tokens = raw_response.usage.total_tokens if hasattr(raw_response, "usage") else 0
        llm_log = LLMCallLog(
            prompt_text=user_prompt,
            response_text=narration,
            model_used="gpt-4o",
            role="narration",
            context_data="basic world and player input only",
            tokens_used=tokens,
            success=True,
            created_at=datetime.now(),
        )
        db.add(llm_log)
        print(f"[INFO] 📚 LLMCallLog entry added. Tokens used: {tokens}")

        # 📝 Add to GameHistory
        history_entry = GameHistory(
            player_input=input.input_text,
            narration=narration,
            timestamp=datetime.now()
        )
        db.add(history_entry)
        print("[INFO] 📝 GameHistory updated with new turn.")
        db.commit()
        print("[INFO] 💾 Database commit successful.")

        return {"narration": narration}

    except Exception as e:
        print("[ERROR] ❌ Exception occurred during turn processing:", e)
        return {"error": str(e)}
