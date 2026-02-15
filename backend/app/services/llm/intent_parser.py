import json
from typing import Any

from app.services.llm.ollama_client import OllamaClient


DEFAULT_INTENT = {"primitive": "unknown", "target": None, "modifiers": []}


class IntentParser:
    def __init__(self, client: OllamaClient, model: str = "mistral"):
        self.client = client
        self.model = model

    def parse(self, text: str) -> dict[str, Any]:
        prompt = f"""
You are an intent parser for a D&D game engine.

Return ONLY valid JSON with this schema:
{{
  "primitive": "move|observe|talk|attack|cast|use_item|unknown",
  "target": "string or null",
  "modifiers": ["array of short strings"]
}}

Rules:
- Output MUST be JSON only.
- If unsure, set primitive="unknown".
- Keep modifiers short.

Player input:
{text}
""".strip()

        try:
            raw = self.client.generate(
                model=self.model,
                prompt=prompt,
                temperature=0.1,
                num_predict=180,
            ).strip()

            # Some models wrap JSON in text; attempt to extract first {...} block
            json_text = self._extract_json_object(raw)
            data = json.loads(json_text)

            # minimal validation
            if not isinstance(data, dict):
                return DEFAULT_INTENT
            if "primitive" not in data:
                return DEFAULT_INTENT
            if "modifiers" in data and not isinstance(data["modifiers"], list):
                data["modifiers"] = []
            if "target" not in data:
                data["target"] = None

            return {
                "primitive": str(data.get("primitive", "unknown")),
                "target": data.get("target", None),
                "modifiers": data.get("modifiers", []),
            }
        except Exception:
            return DEFAULT_INTENT

    @staticmethod
    def _extract_json_object(raw: str) -> str:
        # Find first '{' and last '}' and slice
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            # if not found, force default JSON
            return json.dumps(DEFAULT_INTENT)
        return raw[start : end + 1]
