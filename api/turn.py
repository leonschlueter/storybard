from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from services.narration import build_prompt, call_openai_structured
from services.gm_intent import extract_gm_intent
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

    # 🧠 First, generate GM Intent
    gm_intent = extract_gm_intent(db, client, input.input_text)
    print("[INFO] 🎯 GM Intent:")
    print(gm_intent.model_dump_json(indent=2))  # Pretty-print JSON

    # 📃 Build system prompt with GM intent
    narration_system_prompt = f"""
You are \"Tom\", a sharp-witted and seasoned Game Master (GM) for a text-based D&D 5e game.
You have a dry sense of humor, a deep respect for the rules, and the calm authority of someone who's refereed more tavern brawls than weddings. You narrate in tight, vivid bursts—like you're running a live table. Your goal is to keep the game grounded, immersive, and quick on its feet, with just enough sarcasm to remind the player that anything can happen—and probably will.

Stay in character as Tom at all times. You can joke, tease the player a bit, or make silly comments—but only *around* the action, never at the cost of immersion. Use D&D 5e rules exactly. Roll when rolls are needed. Combat uses initiative, attacks, AC, and hit points. Skill checks follow proper mechanics. If a player asks something chaotic or weird, roll with it like a veteran GM would.

**Narration Guidelines:**
- 2–4 sentences per turn.
- Focus only on what the player perceives or can act on right now.
- No backstory unless investigated.
- Advance the situation slightly each turn.
- Use second-person narration.
- Never assume player action.
- End with tension, a roll, or a beat—not a question.

**GM Intent:**
- Intent: {gm_intent.intention}
- Tone: {gm_intent.tone}
- Risk Level: {gm_intent.narrative_risk}
- Reasoning: {gm_intent.reasoning}
- Tags: {gm_intent.tags or "none"}
"""

    #print("[INFO] 🧠 System prompt prepared.")

    user_prompt = build_prompt(db, input.input_text)
    #print("[INFO] 📜 User prompt built:\n", user_prompt)

    try:
        #print("[INFO] ✨ Sending prompt to OpenAI...")
        narration, raw_response = call_openai_structured(client, narration_system_prompt, user_prompt)
        #print("[INFO] ✅ Narration received:\n", narration)

        tokens = raw_response.usage.total_tokens if hasattr(raw_response, "usage") else 0

        llm_log = LLMCallLog(
            prompt_text=user_prompt,
            response_text=narration,
            model_used="gpt-4o",
            role="narration",
            context_data="player turn and GM intent",
            tokens_used=tokens,
            success=True,
            created_at=datetime.now(),
        )
        db.add(llm_log)

        history_entry = GameHistory(
            player_input=input.input_text,
            narration=narration,
            timestamp=datetime.now()
        )
        db.add(history_entry)
        db.commit()

        print("[INFO] 📀 All data committed to DB.")
        return {"narration": narration}

    except Exception as e:
        print("[ERROR] ❌ Exception occurred:", e)
        return {"error": str(e)}