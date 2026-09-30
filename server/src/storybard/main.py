from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

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

    # AsyncPostgresSaver, not InMemorySaver: a paused turn's in-progress chain state used
    # to live only in the server process's own memory — a restart mid-review orphaned it
    # at the LangGraph level even though its ChainStep/TurnRun rows in Postgres were
    # unaffected (confirmed live: resuming after a restart raised a raw KeyError, a 500,
    # not a clean recoverable error). langgraph-checkpoint-postgres was already a
    # dependency; this was a known, tracked gap, not a final architectural choice.
    # AsyncPostgresSaver wants a plain psycopg conn string, not SQLAlchemy's "+psycopg"
    # dialect-qualified URL — same Postgres, a different driver-string convention.
    pg_conn_string = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(pg_conn_string) as checkpointer:
        # Idempotent — creates LangGraph's own checkpoint tables on first run, a no-op
        # after. Separate from this project's own Alembic-managed schema: LangGraph owns
        # and migrates these tables itself, not app/alembic/versions/.
        await checkpointer.setup()

        # The compiled graph + its checkpointer must be a true singleton for the app's
        # lifetime: resuming a paused turn later (a separate HTTP request, possibly
        # minutes later while a human reviews a step) needs to hit the *same* checkpointer.
        app.state.chain_runtime = build_graph(
            llm=llm_client,
            model=settings.LLM_MODEL_DEFAULT,
            creative_model=settings.LLM_MODEL_CREATIVE,
            checkpointer=checkpointer,
        )
        app.state.llm_client = llm_client

        log.info(
            "startup",
            model=settings.LLM_MODEL_DEFAULT,
            creative_model=settings.LLM_MODEL_CREATIVE,
            lm_studio_base_url=settings.LM_STUDIO_BASE_URL,
            checkpointer="AsyncPostgresSaver",
        )
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
