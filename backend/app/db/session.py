"""
Database session management.

Pattern: Async engine + sessionmaker.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Quiet down aiosqlite's verbose debug output
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


# === Engine setup ===
_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},
)


# === Session factory ===
_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Allow returning objects after commit
    autoflush=False,
)


# === Schema initialization ===
async def init_db() -> None:
    """
    Recreate the local SQLite schema from the current SQLModel metadata.

    This project deliberately treats SQLite as disposable demo state. Every
    backend restart drops all tables, recreates them, and lets startup seeding
    repopulate the mock book. Do not use this lifecycle for persistent data.
    """
    # Import models so they're registered with SQLModel.metadata
    # (must happen before create_all)
    from app.db import models  # noqa: F401
    
    async with _engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    
    logger.info(
        "database_recreated" if _engine.dialect.name == "sqlite" else "database_initialized",
        url=settings.database_url,
        tables=list(SQLModel.metadata.tables.keys()),
    )


# === Session dependency ===
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency: yields a session, commits on success, rolls back on error.
    
    Usage:
        @router.get("/items")
        async def list_items(
            session: AsyncSession = Depends(get_session)
        ):
            ...
    """
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Context manager for non-FastAPI code (e.g., startup scripts).
    
    Usage:
        async with session_scope() as session:
            session.add(item)
    """
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Close the engine. Called at app shutdown."""
    await _engine.dispose()
    logger.info("database_closed")
