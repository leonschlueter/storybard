from __future__ import annotations

from unittest.mock import AsyncMock

from storybard.services.llm.lmstudio_client import LMStudioClient
from storybard.services.llm.schemas import NarratorOut


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _client_with_message(message: dict) -> LMStudioClient:
    client = LMStudioClient()
    fake_payload = {"choices": [{"message": message}]}
    client._client.post = AsyncMock(return_value=_FakeResponse(fake_payload))  # type: ignore[method-assign]
    return client


class TestReasoningContentFallback:
    async def test_uses_content_when_present(self):
        client = _client_with_message({"content": '{"narration": "from content"}', "reasoning_content": ""})
        out = await client.structured_chat(model="m", system="s", user="u", output_model=NarratorOut)
        assert out.narration == "from content"

    async def test_falls_back_to_reasoning_content_when_content_empty(self):
        # Confirmed empirically against qwen/qwen3.8-27b: a schema-constrained response
        # can land entirely in reasoning_content with content=="" — this must not be
        # treated as a hard failure.
        client = _client_with_message(
            {"content": "", "reasoning_content": '{"narration": "from reasoning"}'}
        )
        out = await client.structured_chat(model="m", system="s", user="u", output_model=NarratorOut)
        assert out.narration == "from reasoning"

    async def test_falls_back_when_content_missing_entirely(self):
        client = _client_with_message({"reasoning_content": '{"narration": "from reasoning"}'})
        out = await client.structured_chat(model="m", system="s", user="u", output_model=NarratorOut)
        assert out.narration == "from reasoning"

    async def test_both_empty_raises_lmstudio_error(self):
        from storybard.services.llm.lmstudio_client import LMStudioError

        client = _client_with_message({"content": "", "reasoning_content": ""})
        import pytest

        with pytest.raises(LMStudioError):
            await client.structured_chat(model="m", system="s", user="u", output_model=NarratorOut)
