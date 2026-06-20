"""
Shared pytest fixtures for unit and integration tests.

Integration tests use an in-memory SQLite database and override the
get_session dependency so every request writes to the test DB, not the
application DB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

import app.db.models  # noqa: F401 — registers all SQLModel tables in metadata
import app.db.kyc_baseline  # noqa: F401 — registers entity_snapshots table
from app.db.models import AuditEntryDB, CaseDB, ClientDB
from app.db.session import get_session
from app.main import app


@pytest.fixture
async def db_engine():
    """
    Fresh in-memory SQLite database per test — full schema, zero data.

    StaticPool ensures every session from this engine shares one underlying
    connection and therefore one in-memory database. Without it, each
    connect() call would create a separate :memory: DB and data committed
    by seed_case would be invisible to the API's sessions.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    """
    Shared async session factory.

    Both the client fixture (get_session override) and seed_case use this
    factory so they are guaranteed to operate on the same connection.
    """
    return async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


@pytest.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    """
    HTTP client wired to the in-memory test DB via a get_session override.

    The override follows the same commit/rollback contract as the real
    get_session so session lifecycle behaviour is identical in tests.
    """
    async def _override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
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
        entries = await audit_query("drift_subject_analyzed")
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


@pytest.fixture
async def seed_case(session_factory, client):
    """
    Insert a client directly into the DB then create a case via the HTTP API.

    Depends on `client` to guarantee the get_session override is active before
    any data is written, and to use the same session for the case creation so
    the case is visible to all subsequent API calls.

    Returns a dict with string UUIDs:
        {"client_id": "...", "case_id": "..."}
    """
    client_id = uuid4()

    # Insert the client directly — no POST /clients endpoint exists
    async with session_factory() as session:
        db_client = ClientDB(
            id=client_id,
            full_name="Test Client",
            nationality="CH",
            residence_country="CH",
            primary_jurisdiction="CH",
            risk_tolerance="moderate",
            aum_chf=500_000.0,
            esg_focus=False,
            is_pep=False,
            sanctions_check_passed=True,
            onboarded_at=date(2023, 1, 1),
            profile_data={
                "typical_transaction_hours": list(range(8, 19)),
                "whitelist_wallets": [],
            },
        )
        session.add(db_client)
        await session.commit()

    # Create the case through the API so it lands in the same DB the API reads
    resp = await client.post(
        "/api/v1/cases",
        json={
            "client_id": str(client_id),
            "case_type": "social_engineering",
            "jurisdiction": "CH",
            "context": {
                "summary": "Test social engineering case",
                "data": {
                    "requested_amount_chf": 50_000,
                    "hour_of_day": 14,
                    "destination_country": "CH",
                    "urgency_phrases": [],
                    "counterparty_whitelisted": True,
                },
            },
        },
    )
    assert resp.status_code == 201, f"seed_case failed: {resp.text}"
    case_id = resp.json()["id"]

    return {"client_id": str(client_id), "case_id": case_id}
