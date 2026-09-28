from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

import storybard.domain.all  # noqa: F401  (ensures every model is registered on Base.metadata
# before any test runs — FK string references like Actor.current_node_id ->
# "world_nodes.id" only resolve if the referenced model was imported somewhere; without
# this, running a single test file in isolation can fail on models it never touches.)
from storybard.core.db import SessionLocal
from storybard.services.llm.lmstudio_client import LMStudioClient


@pytest_asyncio.fixture
async def db_session():
    """A real session against the dev Postgres (needed for pgvector/UUID/FK types SQLite
    can't emulate), rolled back at the end so tests never leave data behind. `apply_op`
    only flushes, never commits, so everything stays inside this transaction."""
    async with SessionLocal() as session:
        yield session
        await session.rollback()


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def make_lm_client(content: str) -> LMStudioClient:
    """An LMStudioClient whose HTTP layer is mocked to return `content` as the model's
    message content, without hitting a real LM Studio server."""
    client = LMStudioClient()
    fake_payload = {"choices": [{"message": {"content": content}}]}
    client._client.post = AsyncMock(return_value=_FakeResponse(fake_payload))  # type: ignore[method-assign]
    return client


@pytest.fixture
def lm_client_with():
    def _factory(response_obj: dict) -> LMStudioClient:
        return make_lm_client(json.dumps(response_obj))

    return _factory


@pytest.fixture
def lm_client_malformed():
    def _factory(raw_content: str = "not valid json at all") -> LMStudioClient:
        return make_lm_client(raw_content)

    return _factory


@pytest.fixture
def lm_client_by_model():
    """An LMStudioClient whose structured_chat() is mocked directly (not the HTTP layer),
    returning a canned payload keyed by the requested output_model's class name — needed
    for full-chain tests that call several different schemas in sequence."""

    def _factory(responses_by_model_name: dict[str, dict]) -> LMStudioClient:
        client = LMStudioClient()

        async def fake_structured_chat(*, model, system, user, output_model, temperature=0.2):
            payload = responses_by_model_name[output_model.__name__]
            return output_model.model_validate(payload)

        client.structured_chat = fake_structured_chat  # type: ignore[method-assign]
        return client

    return _factory
