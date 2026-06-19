"""
Shared pytest fixtures for unit and integration tests.

Integration tests use an in-memory SQLite database and override the
get_session dependency so every request writes to the test DB, not the
application DB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

import app.db.models  # noqa: F401 — registers all SQLModel tables in metadata
from app.db.models import AuditEntryDB
from app.db.session import get_session
from app.main import app


@pytest.fixture
async def db_engine():
    """Fresh in-memory SQLite database per test — full schema, zero data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    """
    HTTP client wired to the in-memory test DB via a get_session override.

    The override follows the same commit/rollback contract as the real
    get_session so session lifecycle behaviour is identical in tests.
    """
    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def audit_query(db_engine):
    """
    Returns an async callable that queries audit entries from the test DB.

    Usage in tests:
        entries = await audit_query("drift_customer_analyzed")
    """
    from sqlalchemy import select

    async def _query(event_type: str | None = None) -> list[AuditEntryDB]:
        factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            stmt = select(AuditEntryDB)
            if event_type:
                stmt = stmt.where(AuditEntryDB.event_type == event_type)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    return _query
