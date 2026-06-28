"""FastAPI application — entry point for the RAG v2 chatbot API."""

from __future__ import annotations

import asyncio
import logging
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
from models.mongo_logger import MongoLogger  # noqa: E402
from config.settings import Settings  # noqa: E402
from models.database import create_indexes  # noqa: E402

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------


async def _load_persisted_llm_config(settings: Settings) -> list[str]:
    """Merge Mongo-backed LLM overrides into startup settings."""
    if not settings.mongodb_enabled:
        return []

    from models.database import get_motor_client
    from models.system_config import (
        get_llm_config,
        merge_llm_config_into_settings,
    )

    db = get_motor_client()[settings.mongodb_database]
    db_config = await get_llm_config(db)
    if not db_config:
        return []
    return merge_llm_config_into_settings(settings, db_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic — loads the pipeline once."""
    env_path = _RAG_V2_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)

    settings = Settings()
    try:
        applied_llm_fields = await _load_persisted_llm_config(settings)
        if applied_llm_fields:
            logger.info(
                "Loaded persisted LLM config fields: %s",
                applied_llm_fields,
            )
    except Exception:
        logger.warning(
            "Failed to load persisted LLM config, using environment defaults",
            exc_info=True,
        )

    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file or database")

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

    # ── Redis ────────────────────────────────────────────────────────
    redis_manager = None
    app.state.redis_session = None
    app.state.redis_status = "disabled"
    app.state.rate_limiter = None

    if settings.redis_enabled:
        try:
            from cache.redis_client import RedisManager
            redis_manager = RedisManager.from_settings(settings)
            if redis_manager.ping():
                app.state.redis_status = "ok"
                logger.info("Redis connected")

                # Phase 1: Redis session store
                if settings.use_redis_session:
                    from cache.session_store import RedisSessionStore
                    app.state.redis_session = RedisSessionStore(
                        redis_client=redis_manager.get_client(),
                        mongo_logger=mongo_logger,  # dual-write
                    )
                    logger.info("Redis session store enabled (dual-write)")

                # Phase 1: Rate limiter
                if settings.rate_limit_enabled:
                    from cache.rate_limiter import SlidingWindowRateLimiter
                    app.state.rate_limiter = SlidingWindowRateLimiter(
                        redis_client=redis_manager.get_client(),
                        rpm=settings.rate_limit_rpm,
                        rpd=settings.rate_limit_rpd,
                        alert_threshold=settings.rate_limit_alert_threshold,
                    )
                    logger.info(
                        "Rate limiter enabled: %d rpm, %d rpd",
                        settings.rate_limit_rpm,
                        settings.rate_limit_rpd,
                    )

                # Phase 2: LLM response cache
                app.state.llm_cache = None
                if settings.use_redis_cache:
                    from cache.llm_cache import LLMResponseCache
                    app.state.llm_cache = LLMResponseCache(redis_client=redis_manager.get_client())
                    logger.info("LLM response cache enabled")

                # Phase 2: Conversation history cache
                app.state.history_cache = None
                if settings.use_redis_history:
                    from cache.history_cache import ConversationHistoryCache
                    history_cache = ConversationHistoryCache(redis_client=redis_manager.get_client())
                    app.state.history_cache = history_cache
                    if mongo_logger is not None:
                        mongo_logger.history_cache = history_cache
                    logger.info("Conversation history cache enabled")
            else:
                app.state.redis_status = "failed"
                logger.warning("Redis ping failed — Redis features disabled")
        except ImportError:
            logger.warning("redis package not installed — Redis features disabled")
            app.state.redis_status = "not_installed"
        except Exception:
            logger.warning("Redis init failed", exc_info=True)
            app.state.redis_status = "failed"

    app.state.settings = settings  # for middleware access

    logger.info("Initialising RAG v2 Pipeline (models load once) …")
    loop = asyncio.get_running_loop()
    llm_cache = getattr(app.state, "llm_cache", None)
    app.state.pipeline = await loop.run_in_executor(
        None,
        lambda: RAGPipeline(
            settings=settings,
            mongo_logger=mongo_logger,
            llm_cache=llm_cache,
        ),
    )

    # Create MongoDB indexes (idempotent — safe to call on every startup).
    if mongo_logger is not None:
        try:
            await create_indexes()
            logger.info("MongoDB indexes ensured.")
        except Exception:
            logger.warning("MongoDB index creation failed", exc_info=True)
            app.state.mongo_status = "degraded"  # indexes missing but connected

    # Check MongoDB version for admin stats feature gating
    if mongo_logger is not None:
        try:
            from api.routes.admin_stats import check_mongo_version
            from models.database import get_motor_client, _get_settings
            _, db_name = _get_settings()
            _db = get_motor_client()[db_name]
            await check_mongo_version(_db)
        except Exception:
            logger.warning("MongoDB version check failed", exc_info=True)

    logger.info("Backend ready!")
    
    # Warmup LLM to avoid cold-start latency on first request
    async def warmup_llm():
        from langchain_core.messages import HumanMessage
        await asyncio.sleep(2)   # đợi server ready
        try:
            agent = getattr(app.state.pipeline, "agent", None)
            if agent and hasattr(agent, "_llm"):
                await loop.run_in_executor(None, lambda: agent._llm.invoke([HumanMessage(content="hello")]))
                logger.info("[Warmup] LLM warmed up successfully")
        except Exception as e:
            logger.warning("[Warmup] Failed: %s", e)

    asyncio.create_task(warmup_llm())

    # ── Auto-Crawler Scheduler ──────────────────────────────────
    scheduler = None
    if settings.crawler_enabled:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from scripts.auto_crawler import AutoCrawlPipeline

            # Try to reuse embedders from the RAG pipeline
            bge, e5 = None, None
            pipe = app.state.pipeline
            if hasattr(pipe, "retrieval_service"):
                rs = getattr(pipe, "retrieval_service", None)
                bge = getattr(rs, "bge_embedder", None)
                e5 = getattr(rs, "e5_embedder", None)

            crawl_pipeline = AutoCrawlPipeline(
                settings=settings, bge=bge, e5=e5,
            )

            def _run_crawl():
                try:
                    crawl_pipeline.run()
                except Exception:
                    logger.error("Auto-crawl job failed", exc_info=True)

            scheduler = AsyncIOScheduler()
            scheduler.add_job(
                _run_crawl, "cron",
                hour=settings.crawler_schedule_hour,
                minute=settings.crawler_schedule_minute,
                id="auto_crawl_kehoach",
                replace_existing=True,
                misfire_grace_time=None,
            )
            scheduler.start()
            logger.info(
                "Auto-crawl scheduler started — runs daily at %02d:%02d",
                settings.crawler_schedule_hour,
                settings.crawler_schedule_minute,
            )
        except ImportError:
            logger.warning(
                "apscheduler not installed — auto-crawl disabled. "
                "Install with: pip install apscheduler"
            )
        except Exception:
            logger.error("Failed to start auto-crawl scheduler", exc_info=True)

    yield

    # Shutdown scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    # Shutdown Redis
    if redis_manager is not None:
        redis_manager.close()
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
    from .routes.upload import router as upload_router
    from .routes.exam_schedules import router as exam_schedules_router
    from .routes.bookmark import router as bookmark_router
    from .routes.feedback import router as feedback_router
    from .routes.lookup import router as lookup_router
    from .routes.notification import router as notification_router
    from .routes.notification_admin import router as notification_admin_router
    from .routes.admin_stats import router as admin_stats_router
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
            "http://localhost:19006", # Expo web
            "http://localhost:8081",  # Metro bundler
            "http://10.0.2.2:8000",  # Android emulator
        ],
        allow_origin_regex=(
            r"^http://(localhost|127\.0\.0\.1|10\.0\.2\.2|"
            r"192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"
        ),
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
    app.include_router(upload_router)
    app.include_router(exam_schedules_router)
    app.include_router(bookmark_router)
    app.include_router(feedback_router)
    app.include_router(lookup_router)
    app.include_router(notification_router)
    app.include_router(notification_admin_router)
    app.include_router(admin_stats_router)
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    # Rate-limit middleware MUST be added at build time (Starlette forbids adding
    # middleware after the app has started, and on_event startup hooks are ignored
    # when a lifespan handler is set). The actual limiter instance is created later
    # during lifespan; the middleware resolves it lazily from app.state per request
    # and is a transparent pass-through while it is unavailable.
    from api.middleware.rate_limit import RateLimitMiddleware

    _default_settings = Settings()
    app.add_middleware(
        RateLimitMiddleware,
        rpm=_default_settings.rate_limit_rpm,
        rpd=_default_settings.rate_limit_rpd,
    )

    @app.get("/")
    async def root():
        return {
            "status": "running",
            "service": "RAG v2 Chatbot API",
            "version": "2.0.0",
        }

    return app


app = create_app()
