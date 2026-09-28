from __future__ import annotations

from typing import Type, TypeVar

import httpx
from pydantic import BaseModel

from storybard.core.config import settings

T = TypeVar("T", bound=BaseModel)


class LMStudioError(RuntimeError):
    pass


class LMStudioClient:
    """Talks to LM Studio's local server via its OpenAI-compatible API.

    Structured outputs use response_format={"type": "json_schema", "json_schema": {...}}
    (grammar-constrained at the llama.cpp level, so small local models are syntactically
    reliable but not reliable on field-naming/shape unless the schema itself forces it —
    see spec.md design principle #2).
    """

    def __init__(self, base_url: str | None = None, timeout_s: float = 1000.0) -> None:
        self.base_url = (base_url or settings.LM_STUDIO_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def structured_chat(
        self, *, model: str, system: str, user: str, output_model: Type[T], temperature: float = 0.2
    ) -> T:
        schema = output_model.model_json_schema()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": output_model.__name__, "schema": schema},
            },
        }
        try:
            r = await self._client.post(f"{self.base_url}/chat/completions", json=payload)
            r.raise_for_status()
            out = r.json()
            message = out["choices"][0]["message"]
            content = (message.get("content") or "").strip()
            if not content:
                # Reasoning models (e.g. Qwen3) can put their entire final answer inside
                # reasoning_content and leave content empty when the schema-constrained
                # grammar was satisfied during the "thinking" phase — confirmed empirically
                # against qwen/qwen3.8-27b: content=="" every time, reasoning_content held
                # a complete, valid, well-reasoned WorldUpdateOut. Fall back to it rather
                # than treating an empty content field as a hard failure.
                content = (message.get("reasoning_content") or "").strip()
            return output_model.model_validate_json(content)
        except Exception as e:
            raise LMStudioError(str(e)) from e

    async def embed(self, *, model: str, text: str) -> list[float]:
        payload = {"model": model, "input": text}
        try:
            r = await self._client.post(f"{self.base_url}/embeddings", json=payload)
            r.raise_for_status()
            out = r.json()
            vec = out["data"][0]["embedding"]
            if not isinstance(vec, list):
                raise LMStudioError("No embedding returned")
            return [float(x) for x in vec]
        except Exception as e:
            raise LMStudioError(str(e)) from e
