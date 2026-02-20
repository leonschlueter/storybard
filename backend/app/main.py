from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import structlog

from app.core.logging import configure_logging
from app.core.telemetry import setup_tracing
from app.core.config import settings

from app.db.session import engine
from app.db.base import Base
import app.models.all  # noqa: F401
from sqlalchemy import text

from app.api.router import api_router
from fastapi.middleware.cors import CORSMiddleware

log = structlog.get_logger()

def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Storybard Engine", version="0.1.0")

    # DEV CORS (frontend localhost access)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev only
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    setup_tracing(app, engine)

    @app.on_event("startup")
    def startup():
        # Ensure pgvector extension (safe if Postgres; no-op on SQLite)
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
        except Exception:
            # SQLite or non-privileged DB user; ignore.
            pass
        if settings.DB_AUTOCREATE:
            Base.metadata.create_all(bind=engine)
       
        log.info("startup", db_autocreate=settings.DB_AUTOCREATE)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/metrics")
    def metrics():
        return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    app.include_router(api_router, prefix="/api")

    # Prototype UI (plain HTML/JS) available at /ui
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")

    return app

app = create_app()
