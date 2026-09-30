from __future__ import annotations

import time
from typing import Type, TypeVar

import httpx
import structlog
from pydantic import BaseModel

from storybard.core.config import settings

T = TypeVar("T", bound=BaseModel)

log = structlog.get_logger()


class LMStudioError(RuntimeError):
    pass


class LMStudioClient:
    """Talks to LM Studio's local server via its OpenAI-compatible API.

    Structured outputs use response_format={"type": "json_schema", "json_schema": {...}}
    (grammar-constrained at the llama.cpp level, so small local models are syntactically
    reliable but not reliable on field-naming/shape unless the schema itself forces it —
    see spec.md design principle #2).

    Every call is logged (start, and completion or failure with duration) — this used to
    be a total black box: nothing anywhere logged that a call was even in flight, so a
    genuinely stuck request was indistinguishable from a normal slow one and impossible to
    debug from `docker logs` alone. See the live debugging session that motivated this.
    """

    def __init__(self, base_url: str | None = None, timeout_s: float = 300.0) -> None:
        # Was 1000s (16+ minutes) — generous for slow local reasoning models, but that
        # generous a ceiling means a genuine hang wouldn't surface as an error for a very
        # long time either. 300s is still well above every observed real call (the
        # heaviest seed-narrative calls have taken ~60-90s) while actually bounding how
        # long a stuck request stays silent.
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
        prompt_chars = len(system) + len(user)
        log.info("lmstudio.request_started", model=model, output_model=output_model.__name__, prompt_chars=prompt_chars)
        started = time.monotonic()
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
            result = output_model.model_validate_json(content)
            log.info(
                "lmstudio.request_completed", model=model, output_model=output_model.__name__,
                duration_s=round(time.monotonic() - started, 1),
            )
            return result
        except Exception as e:
            log.error(
                "lmstudio.request_failed", model=model, output_model=output_model.__name__,
                duration_s=round(time.monotonic() - started, 1), error=str(e),
            )
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
