# services/gm_intent.py
from openai import OpenAI
from schemas.gm_intent import GMIntent
from textwrap import dedent
from sqlalchemy.orm import Session
from database.history.history import GameHistory

def extract_gm_intent(db: Session, client: OpenAI, player_input: str) -> GMIntent:
    system_prompt = dedent("""
        You are an experienced Dungeons & Dragons Game Master AI responsible for interpreting player input
        and generating a clear, structured narrative plan for the next scene. Your job is to describe
        the GM's intent behind the next turn, including tone, pacing, risks, and any thematic or
        narrative goals. Be really descriptive and specific about the intent, not just the action, also be creative and engaging.

        Respond ONLY using the structured format provided. Do not include any prose or explanation. Consider the whole history and add implication and/or interesting twists to the scene.

        Use the following fields:
        - intention: What is the GM trying to achieve in the next beat?
        - tone: The mood (e.g., tense, lighthearted, mysterious)
        - pacing_goal: Slow burn, sudden danger, exploration, etc.
        - narrative_risk: % chance something could go wrong (0–100)
        - impact_estimate: How important is this scene? ("minor", "moderate", "high")
        - reasoning: Why this is the right next beat for the scene
        - target_type / target_id: Optional — if part of a larger thread
        - is_active / is_consumed: Just leave false
        - priority: default 50 unless you think it's urgent
        - tags: Optional — string of keywords
    """)
    history = (
        db.query(GameHistory)
        .order_by(GameHistory.timestamp.desc())
        .limit(10)
        .all()
    )[::-1]  # reverse to chronological order

    chat = ""
    for entry in history:
        if entry.player_input:
            chat += f"\nPlayer: {entry.player_input}"
        if entry.narration:
            chat += f"\nNarrator: {entry.narration}"

    chat += f"Player: {player_input}\n"
    user_prompt = f'History: {chat} \n Player input: "{player_input}"\n\nReturn the detailed GMIntent.'
    print(user_prompt)
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            response_format=GMIntent,
        )


        return response.choices[0].message.parsed
    
    except Exception as e:
        print("[ERROR] Failed to extract GMIntent:", e)
        return GMIntent(
            intention="Move the story forward based on player input.",
            tone="neutral",
            pacing_goal="default pacing",
            narrative_risk=10,
            impact_estimate="minor",
            reasoning="Fallback intent due to error.",
        )
