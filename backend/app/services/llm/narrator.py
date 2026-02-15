from app.services.llm.ollama_client import OllamaClient


class Narrator:
    def __init__(self, client: OllamaClient, model: str = "mistral"):
        self.client = client
        self.model = model

    def narrate(
        self,
        *,
        actor_name: str,
        location_name: str | None,
        action_text: str,
        tone: dict | None = None,
        intent: dict | None = None,
    ) -> str:
        tone = tone or {"style": "neutral fantasy"}
        intent = intent or {}

        prompt = f"""
You are a D&D dungeon master. Write 2-6 sentences.

Context:
- Player: {actor_name}
- Location: {location_name or "Unknown"}
- Tone: {tone}

Player action:
"{action_text}"

Interpreted intent (for you, not to reveal as JSON):
{intent}

Requirements:
- Stay grounded (no teleporting outcomes).
- Describe immediate sensory details + 1 actionable follow-up prompt/question.
""".strip()

        try:
            out = self.client.generate(
                model=self.model,
                prompt=prompt,
                temperature=0.7,
                num_predict=220,
            ).strip()
            return out or f"{actor_name} acts, but the world remains quiet."
        except Exception:
            # fallback
            return f"{actor_name} tries to '{action_text}'. Something in {location_name or 'the area'} catches your attention."
