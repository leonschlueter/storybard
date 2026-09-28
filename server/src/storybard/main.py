from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from storybard.api import campaigns, explore, party, turns, ws
from storybard.chain.graph import build_graph
from storybard.core.config import settings
from storybard.core.logging import configure_logging
from storybard.services.llm.lmstudio_client import LMStudioClient

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    llm_client = LMStudioClient()
    # The compiled graph + its InMemorySaver checkpointer must be a true singleton for the
    # app's lifetime: resuming a paused turn later (a separate HTTP request, possibly
    # minutes later while a human reviews a step) needs to hit the *same* checkpointer
    # instance that holds that turn's in-memory state.
    app.state.chain_runtime = build_graph(llm=llm_client, model=settings.LLM_MODEL_DEFAULT)
    app.state.llm_client = llm_client

    log.info("startup", model=settings.LLM_MODEL_DEFAULT, lm_studio_base_url=settings.LM_STUDIO_BASE_URL)
    yield

    await llm_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Storybard v2", version="0.1.0", lifespan=lifespan)

    # Dev-only permissive CORS (frontend runs on a separate Vite dev server port).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(campaigns.router, prefix="/api/v1")
    app.include_router(explore.router, prefix="/api/v1")
    app.include_router(party.router, prefix="/api/v1")
    app.include_router(turns.router, prefix="/api/v1")
    app.include_router(ws.router, prefix="/api/v1")

    return app


app = create_app()
