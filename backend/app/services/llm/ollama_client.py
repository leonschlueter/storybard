import requests
from typing import Any

from app.core.config import settings


class OllamaClient:
    """
    Minimal Ollama HTTP client.
    - generate() returns plain text model output
    """
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or getattr(settings, "OLLAMA_URL", None) or "http://localhost:11434").rstrip("/")

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        temperature: float = 0.1,
        num_predict: int = 256,
        stream: bool = False,
        extra_options: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        if extra_options:
            payload["options"].update(extra_options)

        r = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")
