from __future__ import annotations

import time
from typing import Type, TypeVar, Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.metrics import LLM_CALL_COUNTER, LLM_SECONDS

T = TypeVar("T", bound=BaseModel)

class OllamaError(RuntimeError):
    pass

class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout_s: float = 1000.0):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._client = httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def chat_text(self, *, model: str, system: str, user: str, temperature: float = 0.7) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        t0 = time.perf_counter()
        try:
            r = self._client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            out = r.json()
            content = out.get("message", {}).get("content", "")
            LLM_CALL_COUNTER.labels(role="text", status="ok").inc()
            return content
        except Exception as e:
            LLM_CALL_COUNTER.labels(role="text", status="error").inc()
            raise OllamaError(str(e)) from e
        finally:
            LLM_SECONDS.labels(role="text").observe(time.perf_counter() - t0)

    def structured_chat(self, *, model: str, system: str, user: str, output_model: Type[T], temperature: float = 0.2) -> T:
        schema = output_model.model_json_schema()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "options": {"temperature": temperature},
        }
        t0 = time.perf_counter()
        try:
            r = self._client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            out = r.json()
            content = out.get("message", {}).get("content", "")
            obj = output_model.model_validate_json(content)
            LLM_CALL_COUNTER.labels(role=output_model.__name__, status="ok").inc()
            return obj
        except Exception as e:
            LLM_CALL_COUNTER.labels(role=output_model.__name__, status="error").inc()
            raise OllamaError(str(e)) from e
        finally:
            LLM_SECONDS.labels(role=output_model.__name__).observe(time.perf_counter() - t0)
