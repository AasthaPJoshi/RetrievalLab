# =============================================================================
# RetrievalLab — backend/db/base.py
# =============================================================================
# PURPOSE : Creates the async SQLAlchemy engine and session factory that every
#           database operation in the codebase shares.
#
# DESIGN DECISIONS:
#   • Uses asyncpg as the async PostgreSQL driver (fastest pure-Python driver).
#   • Single engine per process (connection pool is reused across requests).
#   • `get_db()` is a FastAPI dependency — yields a session per request,
#     auto-commits on success, rolls back on exception.
#   • `Base` is the declarative base — all ORM models inherit from it.
#
# USAGE:
#   # In a FastAPI route:
#   from backend.db.base import get_db
#   async def my_route(db: AsyncSession = Depends(get_db)):
#       result = await db.execute(select(MyModel))
#
#   # In standalone scripts / tests:
#   async with AsyncSessionLocal() as session:
#       ...
#
# INPUT  : DATABASE_URL environment variable (via Settings)
# OUTPUT : SQLAlchemy AsyncEngine, AsyncSessionLocal factory, Base class
# =============================================================================

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings

settings = get_settings()

# ─── Engine ──────────────────────────────────────────────────────────────────
# pool_size=10: max 10 persistent connections (good for dev + moderate load)
# max_overflow=20: up to 20 additional connections under burst load
# pool_pre_ping=True: validates connections before checkout (avoids stale conn errors)
engine = create_async_engine(
    settings.database.url,
    echo=settings.is_development,    # log SQL queries in dev mode only
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,               # recycle connections every hour
    json_serializer=lambda obj: __import__("orjson").dumps(obj).decode(),
    json_deserializer=lambda s: __import__("orjson").loads(s),
)


# ─── Session Factory ─────────────────────────────────────────────────────────
# expire_on_commit=False: don't expire objects after commit so we can still
#                         read attributes in the same request without re-querying.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,                 # manual flush gives us explicit control
    autocommit=False,
)


# ─── Declarative Base ────────────────────────────────────────────────────────
class Base(AsyncAttrs, DeclarativeBase):
    """
    Shared base class for all ORM models.

    AsyncAttrs mixin enables `await model.awaitable_attrs.relationship`
    for lazy-loading async relationships.
    """
    # Type annotation for metadata — subclasses don't need to repeat this.
    type_annotation_map: dict[Any, Any] = {}


# ─── FastAPI Dependency ──────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional database session.

    Pattern:
        - Begin transaction on entry.
        - Yield session to the route handler.
        - Commit if handler completes without exception.
        - Rollback + re-raise if any exception occurs.
        - Always close the session (returns connection to pool).

    Usage:
        from fastapi import Depends
        from backend.db.base import get_db

        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Active database session with open transaction.

    Raises:
        Any exception raised in the route handler (after rollback).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Health check helper ─────────────────────────────────────────────────────
async def check_db_connection() -> bool:
    """
    Verify the database is reachable and pgvector is installed.

    Returns:
        True if DB is healthy, False otherwise.
        Called by the /health endpoint on startup.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            # Verify pgvector extension is available
            result = await session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            pgvector_installed = result.scalar() is not None
            return pgvector_installed
    except Exception:
        return False
