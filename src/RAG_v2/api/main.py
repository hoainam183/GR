"""FastAPI application — entry point for the RAG v2 chatbot API."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure RAG_v2 root is importable
_RAG_V2_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAG_V2_ROOT))

from pipeline.rag_pipeline import RAGPipeline  # noqa: E402
from pipeline.mongo_logger import MongoLogger  # noqa: E402
from config.settings import Settings  # noqa: E402
from models.database import create_indexes  # noqa: E402

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic — loads the pipeline once."""
    env_path = _RAG_V2_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")

    settings = Settings()

    # MongoDB logger
    mongo_logger: MongoLogger | None = None
    if settings.mongodb_enabled:
        try:
            mongo_logger = MongoLogger(
                uri=settings.mongodb_uri,
                database=settings.mongodb_database,
            )
            app.state.mongo_logger = mongo_logger
            app.state.mongo_status = "ok"
        except Exception:
            logger.warning(
                "MongoLogger init failed, logging disabled", exc_info=True
            )
            app.state.mongo_logger = None
            app.state.mongo_status = "failed"  # visible to /health
    else:
        app.state.mongo_logger = None
        app.state.mongo_status = "disabled"

    logger.info("Initialising RAG v2 Pipeline (models load once) …")
    loop = asyncio.get_running_loop()
    app.state.pipeline = await loop.run_in_executor(
        None,
        lambda: RAGPipeline(api_key=api_key, mongo_logger=mongo_logger),
    )

    # Create MongoDB indexes (idempotent — safe to call on every startup).
    if mongo_logger is not None:
        try:
            await create_indexes()
            logger.info("MongoDB indexes ensured.")
        except Exception:
            logger.warning("MongoDB index creation failed", exc_info=True)
            app.state.mongo_status = "degraded"  # indexes missing but connected

    logger.info("Backend ready!")
    yield
    logger.info("Shutting down …")


# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    from .routes.chat import router as chat_router
    from .routes.health import router as health_router
    from .routes.session import router as session_router
    from .routes.metrics import router as metrics_router
    from .routes.retrieval import router as retrieval_router
    from routers.auth import router as auth_router

    app = FastAPI(
        title="RAG v2 Chatbot API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:8080",  # Docker / nginx frontend
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    app.include_router(chat_router)
    app.include_router(health_router)
    app.include_router(session_router)
    app.include_router(metrics_router)
    app.include_router(retrieval_router)
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    @app.get("/")
    async def root():
        return {
            "status": "running",
            "service": "RAG v2 Chatbot API",
            "version": "2.0.0",
        }

    return app


app = create_app()
