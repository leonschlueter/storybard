from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.actor import Actor
from app.models.events import Event
from app.models.world import WorldNode

from app.services.llm.ollama_client import OllamaClient
from app.services.llm.intent_parser import IntentParser
from app.services.llm.narrator import Narrator


class ActionEngine:
    def __init__(self):
        client = OllamaClient()
        # You can later split models: small for intent, larger for narration
        self.intent_parser = IntentParser(client, model="mistral")
        self.narrator = Narrator(client, model="mistral")

    def handle(self, *, actor_id: str, text: str, db: Session) -> dict[str, Any]:
        actor = db.execute(select(Actor).where(Actor.id == actor_id)).scalar_one_or_none()
        if not actor:
            return {"error": "Actor not found"}

        location_name = None
        if actor.current_node_id:
            node = db.execute(select(WorldNode).where(WorldNode.id == actor.current_node_id)).scalar_one_or_none()
            location_name = node.name if node else None

        # 1) MicroLLM parse intent (structured)
        intent = self.intent_parser.parse(text)

        # 2) (For MVP) do no deterministic simulation changes yet
        result_data: dict[str, Any] = {
            "ok": True,
            "note": "MVP: no mechanics applied yet",
        }

        # 3) Narrate
        tone = {"style": "neutral fantasy"}  # later: campaign.tone_vector
        narration = self.narrator.narrate(
            actor_name=actor.name,
            location_name=location_name,
            action_text=text,
            tone=tone,
            intent=intent,
        )

        # 4) Persist event
        event = Event(
            campaign_id=actor.campaign_id,
            actor_id=actor.id,
            action_text=text,
            parsed_intent=intent,
            result_data=result_data,
            narration_text=narration,
        )
        db.add(event)
        db.commit()

        return {
            "actor_id": str(actor.id),
            "intent": intent,
            "result": result_data,
            "narration": narration,
        }


action_engine = ActionEngine()
