# =============================================================================
# RetrievalLab — backend/api/v1/endpoints/health.py
# =============================================================================
# PURPOSE : /health endpoint for service liveness/readiness checks.
#           Used by Docker healthchecks, Kubernetes probes, and monitoring.
#
# ENDPOINTS:
#   GET /api/v1/health        → full component health with details
#   GET /api/v1/health/live   → minimal liveness probe (200 = app is running)
#   GET /api/v1/health/ready  → readiness probe (200 = app can serve traffic)
#
# HEALTH CHECKS PERFORMED:
#   • Database (PostgreSQL) — query SELECT 1 + pgvector extension check
#   • Cache (Redis)         — PING command
#   • Object storage (MinIO) — bucket reachability
#   • ChromaDB             — heartbeat endpoint
#
# RESPONSE CODES:
#   200 — all checks pass (or at least DB + cache pass for /ready)
#   503 — one or more critical components unhealthy
# =============================================================================

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
router = APIRouter()


class ComponentHealth(BaseModel):
    """Health status of a single infrastructure component."""
    name:       str
    status:     str       # "healthy" | "degraded" | "unhealthy"
    latency_ms: float | None = None
    detail:     str | None   = None


class HealthResponse(BaseModel):
    """Full health check response."""
    status:     str                      # "healthy" | "degraded" | "unhealthy"
    version:    str
    components: list[ComponentHealth]
    uptime_s:   float


# Track app start time for uptime reporting
_START_TIME = time.time()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Full health check",
    description="Checks connectivity to all infrastructure components.",
)
async def health_check() -> JSONResponse:
    """
    Check connectivity to all infrastructure components.

    Returns 200 with status="healthy" if all components pass.
    Returns 503 with status="degraded"/"unhealthy" if any fail.
    """
    checks = await _run_all_checks()

    # Determine overall status
    statuses = {c.status for c in checks}
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    response = HealthResponse(
        status     = overall,
        version    = "0.1.0",
        components = checks,
        uptime_s   = round(time.time() - _START_TIME, 1),
    )

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(content=response.model_dump(), status_code=status_code)


@router.get("/health/live", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Minimal liveness probe — always returns 200 if app is running."""
    return {"status": "alive"}


@router.get("/health/ready", summary="Readiness probe")
async def readiness() -> JSONResponse:
    """
    Readiness probe — checks only critical components (DB + cache).
    Returns 200 if app is ready to serve traffic.
    """
    db_check    = await _check_database()
    redis_check = await _check_redis()

    ready = db_check.status == "healthy" and redis_check.status == "healthy"
    status_code = 200 if ready else 503

    return JSONResponse(
        content={"status": "ready" if ready else "not_ready"},
        status_code=status_code,
    )


# ─── Component Checkers ───────────────────────────────────────────────────────

async def _run_all_checks() -> list[ComponentHealth]:
    """Run all component health checks concurrently."""
    import asyncio
    results = await asyncio.gather(
        _check_database(),
        _check_redis(),
        _check_minio(),
        _check_chromadb(),
        return_exceptions=False,
    )
    return list(results)


async def _check_database() -> ComponentHealth:
    """Check PostgreSQL + pgvector availability."""
    t0 = time.perf_counter()
    try:
        from backend.db.base import check_db_connection
        ok = await check_db_connection()
        latency = round((time.perf_counter() - t0) * 1000, 2)
        if ok:
            return ComponentHealth(name="postgresql", status="healthy", latency_ms=latency)
        else:
            return ComponentHealth(
                name="postgresql",
                status="unhealthy",
                latency_ms=latency,
                detail="pgvector extension not installed",
            )
    except Exception as exc:
        return ComponentHealth(
            name="postgresql",
            status="unhealthy",
            detail=str(exc),
        )


async def _check_redis() -> ComponentHealth:
    """Check Redis via PING."""
    t0 = time.perf_counter()
    try:
        import redis.asyncio as aioredis
        from config.settings import get_settings
        settings = get_settings()
        client = aioredis.from_url(settings.redis.url)
        await client.ping()
        await client.aclose()
        latency = round((time.perf_counter() - t0) * 1000, 2)
        return ComponentHealth(name="redis", status="healthy", latency_ms=latency)
    except Exception as exc:
        return ComponentHealth(name="redis", status="unhealthy", detail=str(exc))


async def _check_minio() -> ComponentHealth:
    """Check MinIO bucket reachability."""
    t0 = time.perf_counter()
    try:
        import httpx
        from config.settings import get_settings
        settings = get_settings()
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"http://{settings.minio.endpoint}/minio/health/live"
            )
        latency = round((time.perf_counter() - t0) * 1000, 2)
        status = "healthy" if response.status_code == 200 else "degraded"
        return ComponentHealth(name="minio", status=status, latency_ms=latency)
    except Exception as exc:
        return ComponentHealth(name="minio", status="degraded", detail=str(exc))


async def _check_chromadb() -> ComponentHealth:
    """Check ChromaDB heartbeat."""
    t0 = time.perf_counter()
    try:
        import httpx
        from config.settings import get_settings
        settings = get_settings()
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.chroma.url}/api/v1/heartbeat")
        latency = round((time.perf_counter() - t0) * 1000, 2)
        status = "healthy" if response.status_code == 200 else "degraded"
        return ComponentHealth(name="chromadb", status=status, latency_ms=latency)
    except Exception as exc:
        return ComponentHealth(name="chromadb", status="degraded", detail=str(exc))
