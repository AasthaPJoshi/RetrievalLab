# =============================================================================
# RetrievalLab — backend/main.py
# =============================================================================
# PURPOSE : FastAPI application factory and entry point.
#           Creates the ASGI app, registers all routers, sets up middleware,
#           configures structured logging, and exposes health/metrics endpoints.
#
# STARTUP SEQUENCE:
#   1. Configure structlog (JSON in prod, pretty in dev)
#   2. Create FastAPI app with OpenAPI metadata
#   3. Add middleware (CORS, request ID, timing)
#   4. Register all API routers under /api/v1/
#   5. Register startup/shutdown lifecycle hooks (DB connection pool)
#   6. Expose /health and /metrics endpoints
#
# HOW TO RUN:
#   Development:
#     uvicorn backend.main:app --reload --port 8000
#   Production:
#     uvicorn backend.main:app --workers 4 --port 8000
#
# AFTER THIS FILE: Requests flow to routers → services → DB/vector stores.
# API docs available at: http://localhost:8000/docs (Swagger)
#                        http://localhost:8000/redoc (ReDoc)
# =============================================================================

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from config.settings import get_settings
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.v1.endpoints import agent as agent_router

# Import routers (created in their respective files)
from backend.api.v1.endpoints import corpus as corpus_router
from backend.api.v1.endpoints import eval as eval_router
from backend.api.v1.endpoints import health as health_router
from backend.api.v1.endpoints import retrieve as retrieve_router
from backend.db.base import check_db_connection

settings = get_settings()

# ─── Structured Logging Setup ─────────────────────────────────────────────────
# Must be configured before the first log call anywhere in the process.


def _configure_logging() -> None:
    """
    Configure structlog for the application.

    Dev mode: pretty-printed, colorized output for readability.
    Prod mode: JSON newline-delimited format for log aggregators (Loki, CloudWatch).
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,  # merge request-scoped context
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            __import__("logging").getLevelName(settings.log_level)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_configure_logging()
logger = structlog.get_logger(__name__)


# ─── Lifespan (replaces on_event startup/shutdown) ───────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Runs startup code before yield, shutdown code after yield.
    """
    # ── STARTUP ──────────────────────────────────────────────────────────
    logger.info("startup_begin", app=settings.app_name, env=settings.app_env)

    # Verify database connectivity
    db_healthy = await check_db_connection()
    if not db_healthy:
        logger.error("database_unreachable_on_startup")
        # Don't raise — let the app start; /health will report degraded state.

    # Initialize MinIO bucket if not exists
    try:
        from backend.utils.storage import ensure_bucket_exists

        await ensure_bucket_exists()
    except Exception as exc:
        logger.warning("minio_bucket_init_failed", error=str(exc))

    logger.info("startup_complete", db_healthy=db_healthy)

    yield  # Application runs here

    # ── SHUTDOWN ─────────────────────────────────────────────────────────
    logger.info("shutdown_begin")
    # SQLAlchemy disposes the connection pool automatically
    # Redis connections are closed by redis-py on GC
    logger.info("shutdown_complete")


# ─── Application Factory ──────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Fully configured FastAPI instance.
    """
    app = FastAPI(
        title="RetrievalLab API",
        description=(
            "Cross-industry retrieval research platform. "
            "Benchmark, stress-test, and advance RAG retrieval systems."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS Middleware ───────────────────────────────────────────────────
    # Allow the React frontend dev server (localhost:3000/5173) in development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"]
        if settings.is_development
        else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID + Timing Middleware ────────────────────────────────────
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:
        """
        Assign a unique request ID and timing to every request.

        The request_id is added to:
        - Response headers (X-Request-ID) — for client-side correlation
        - structlog contextvars — included in all log lines for this request
        """
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Bind request_id to all log lines within this request's context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Duration-Ms"] = str(duration_ms)

        logger.info(
            "request_complete",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response

    # ── Exception Handlers ────────────────────────────────────────────────
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Return 400 for business logic validation errors."""
        logger.warning("validation_error", error=str(exc))
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return 500 for unexpected errors (log full traceback)."""
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Check logs for details."},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health_router.router, prefix="/api/v1", tags=["Health"])
    app.include_router(corpus_router.router, prefix="/api/v1/corpus", tags=["Corpus"])
    app.include_router(retrieve_router.router, prefix="/api/v1/retrieve", tags=["Retrieve"])
    app.include_router(eval_router.router, prefix="/api/v1/eval", tags=["Evaluation"])
    app.include_router(agent_router.router, prefix="/api/v1/agent", tags=["Agent"])

    logger.info("routers_registered")
    return app


# ─── App Instance ─────────────────────────────────────────────────────────────
# This is what uvicorn imports: `uvicorn backend.main:app`
app = create_app()
