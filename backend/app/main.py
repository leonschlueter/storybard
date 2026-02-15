from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Keep this lightweight.
    """
    # ---- Startup ----
    print("Starting DnD Engine API...")
    init_db()
    yield
    # ---- Shutdown ----
    print("Shutting down DnD Engine API...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Storybard",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- API Routes ----
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
