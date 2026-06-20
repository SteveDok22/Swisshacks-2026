"""
Tests for db/kyc_baseline.py — EntitySnapshot store/load operations.

Covers:
- store_snapshot: persists a row and returns it
- load_latest_snapshot: returns the most-recently-inserted row
- load_onboarding_snapshot: returns the oldest onboarding-type row
- load_snapshot_history: returns all rows newest-first
- load_all_baselines: returns latest snapshot per customer as a dict
- Seeding: seed_if_empty populates the entity_snapshots table from the
  synthetic book; each customer in the book gets exactly one baseline row.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select

import app.db.models  # noqa: F401 — register all tables
import app.db.kyc_baseline  # noqa: F401 — register entity_snapshots table
from app.db.kyc_baseline import (
    EntitySnapshotDB,
    load_all_baselines,
    load_latest_snapshot,
    load_onboarding_snapshot,
    load_snapshot_history,
    store_snapshot,
)
from app.drift.simulator import generate_book


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def engine():
    """In-memory SQLite DB per test — full schema, zero data."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    """Single session for a test — committed on exit."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with factory() as s:
        yield s
        await s.commit()


def _make_snapshot(
    drift_id: str = "drift-001",
    snapshot_type: str = "onboarding",
    name: str = "Test Corp AG",
    days_offset: int = 0,
) -> EntitySnapshotDB:
    return EntitySnapshotDB(
        drift_id=drift_id,
        snapshot_date=date(2023, 1, 1) + timedelta(days=days_offset),
        snapshot_type=snapshot_type,
        source="internal",
        name=name,
        jurisdiction="CH",
        dissolution_status="active",
        avg_monthly_volume_chf=50_000.0,
        counterparty_risk_mean=0.08,
        corridor_risk_mean=0.05,
        margin_ratio_mean=0.25,
    )


# ---------------------------------------------------------------------------
# store_snapshot
# ---------------------------------------------------------------------------


class TestStoreSnapshot:
    async def test_returns_the_stored_row(self, session):
        snap = _make_snapshot()
        result = await store_snapshot(session, snap)
        assert result is snap

    async def test_row_is_queryable_after_flush(self, session):
        snap = _make_snapshot(drift_id="drift-042")
        await store_snapshot(session, snap, flush=True)
        row = await session.get(EntitySnapshotDB, snap.id)
        assert row is not None
        assert row.drift_id == "drift-042"

    async def test_multiple_snapshots_same_customer(self, session):
        s1 = _make_snapshot(drift_id="c-1", snapshot_type="onboarding")
        s2 = _make_snapshot(drift_id="c-1", snapshot_type="annual_review", days_offset=365)
        await store_snapshot(session, s1, flush=True)
        await store_snapshot(session, s2, flush=True)
        result = await session.execute(
            select(EntitySnapshotDB).where(EntitySnapshotDB.drift_id == "c-1")
        )
        assert len(result.scalars().all()) == 2


# ---------------------------------------------------------------------------
# load_latest_snapshot
# ---------------------------------------------------------------------------


class TestLoadLatestSnapshot:
    async def test_returns_none_for_unknown_customer(self, session):
        assert await load_latest_snapshot(session, "unknown") is None

    async def test_returns_the_only_snapshot(self, session):
        snap = _make_snapshot(drift_id="c-2")
        await store_snapshot(session, snap, flush=True)
        result = await load_latest_snapshot(session, "c-2")
        assert result is not None
        assert result.id == snap.id

    async def test_returns_latest_by_insertion_order(self, session):
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s1 = _make_snapshot(drift_id="c-3", snapshot_type="onboarding")
        s1.created_at = t0
        s2 = _make_snapshot(drift_id="c-3", snapshot_type="annual_review")
        s2.created_at = t0 + timedelta(seconds=1)  # guarantee ordering
        await store_snapshot(session, s1, flush=True)
        await store_snapshot(session, s2, flush=True)
        result = await load_latest_snapshot(session, "c-3")
        assert result is not None
        assert result.snapshot_type == "annual_review"

    async def test_does_not_return_other_customer(self, session):
        await store_snapshot(session, _make_snapshot(drift_id="cx"), flush=True)
        assert await load_latest_snapshot(session, "cy") is None


# ---------------------------------------------------------------------------
# load_onboarding_snapshot
# ---------------------------------------------------------------------------


class TestLoadOnboardingSnapshot:
    async def test_returns_none_for_unknown_customer(self, session):
        assert await load_onboarding_snapshot(session, "unk") is None

    async def test_returns_none_when_only_annual_review_exists(self, session):
        # Only annual_review rows — no baseline anchor — must return None.
        await store_snapshot(
            session,
            _make_snapshot(drift_id="c-4", snapshot_type="annual_review"),
            flush=True,
        )
        assert await load_onboarding_snapshot(session, "c-4") is None

    async def test_matches_onboarding_type(self, session):
        s = _make_snapshot(drift_id="c-4b", snapshot_type="onboarding")
        await store_snapshot(session, s, flush=True)
        result = await load_onboarding_snapshot(session, "c-4b")
        assert result is not None
        assert result.snapshot_type == "onboarding"

    async def test_matches_seeded_type(self, session):
        # "seeded" rows are the synthetic-book equivalent of onboarding baselines.
        s = _make_snapshot(drift_id="c-4c", snapshot_type="seeded")
        await store_snapshot(session, s, flush=True)
        result = await load_onboarding_snapshot(session, "c-4c")
        assert result is not None
        assert result.snapshot_type == "seeded"

    async def test_returns_first_onboarding_when_multiple(self, session):
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s1 = _make_snapshot(drift_id="c-5", snapshot_type="onboarding")
        s1.created_at = t0
        await store_snapshot(session, s1, flush=True)
        # A second onboarding snapshot added later (rare but possible in re-KYC)
        s2 = _make_snapshot(drift_id="c-5", snapshot_type="onboarding", days_offset=90)
        s2.created_at = t0 + timedelta(seconds=1)
        await store_snapshot(session, s2, flush=True)
        result = await load_onboarding_snapshot(session, "c-5")
        assert result is not None
        assert result.id == s1.id  # oldest one


# ---------------------------------------------------------------------------
# load_snapshot_history
# ---------------------------------------------------------------------------


class TestLoadSnapshotHistory:
    async def test_empty_for_unknown_customer(self, session):
        assert await load_snapshot_history(session, "unk") == []

    async def test_returns_all_snapshots_newest_first(self, session):
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        types = ("onboarding", "annual_review", "triggered")
        snaps = [_make_snapshot(drift_id="c-6", snapshot_type=t) for t in types]
        for i, s in enumerate(snaps):
            s.created_at = t0 + timedelta(seconds=i)
            await store_snapshot(session, s, flush=True)
        history = await load_snapshot_history(session, "c-6")
        assert len(history) == 3
        # Newest-first: triggered was inserted last
        assert history[0].snapshot_type == "triggered"
        assert history[-1].snapshot_type == "onboarding"

    async def test_does_not_include_other_customer_rows(self, session):
        await store_snapshot(session, _make_snapshot(drift_id="ca"), flush=True)
        await store_snapshot(session, _make_snapshot(drift_id="cb"), flush=True)
        assert len(await load_snapshot_history(session, "ca")) == 1


# ---------------------------------------------------------------------------
# load_all_baselines
# ---------------------------------------------------------------------------


class TestLoadAllBaselines:
    async def test_empty_when_no_snapshots(self, session):
        assert await load_all_baselines(session) == {}

    async def test_one_entry_per_customer(self, session):
        for cid in ("d-1", "d-2", "d-3"):
            await store_snapshot(session, _make_snapshot(drift_id=cid), flush=True)
        result = await load_all_baselines(session)
        assert set(result.keys()) == {"d-1", "d-2", "d-3"}

    async def test_returns_latest_per_customer(self, session):
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        s1 = _make_snapshot(drift_id="d-4", snapshot_type="onboarding")
        s1.created_at = t0
        s2 = _make_snapshot(drift_id="d-4", snapshot_type="annual_review")
        s2.created_at = t0 + timedelta(seconds=1)
        await store_snapshot(session, s1, flush=True)
        await store_snapshot(session, s2, flush=True)
        result = await load_all_baselines(session)
        assert result["d-4"].snapshot_type == "annual_review"


# ---------------------------------------------------------------------------
# EntitySnapshotDB field validation
# ---------------------------------------------------------------------------


class TestEntitySnapshotFields:
    def test_defaults_are_safe(self):
        s = EntitySnapshotDB(
            drift_id="x",
            snapshot_date=date.today(),
            name="Test Entity",
        )
        assert s.beneficial_owners == []
        assert s.officers == []
        assert s.is_pep is False
        assert s.sanctions_check_passed is True
        assert s.raw_data == {}
        assert s.dissolution_status is None

    def test_behavioral_baseline_fields_stored(self):
        s = EntitySnapshotDB(
            drift_id="y",
            snapshot_date=date.today(),
            name="Baseline Corp",
            avg_monthly_volume_chf=12_345.67,
            counterparty_risk_mean=0.12,
            corridor_risk_mean=0.07,
            margin_ratio_mean=0.22,
        )
        assert s.avg_monthly_volume_chf == pytest.approx(12_345.67)
        assert s.counterparty_risk_mean == pytest.approx(0.12)
        assert s.corridor_risk_mean == pytest.approx(0.07)
        assert s.margin_ratio_mean == pytest.approx(0.22)

    def test_raw_data_accepts_arbitrary_dict(self):
        s = EntitySnapshotDB(
            drift_id="z",
            snapshot_date=date.today(),
            name="Raw Corp",
            raw_data={"lei": "529900T8BM49AURSDO55", "ubo_count": 3},
        )
        assert s.raw_data["lei"] == "529900T8BM49AURSDO55"


# ---------------------------------------------------------------------------
# Seeding integration
# ---------------------------------------------------------------------------


class TestKycBaselineSeeding:
    """
    Verify that _seed_kyc_baselines (called by seed_if_empty) populates one
    EntitySnapshot per synthetic customer and that behavioral baseline fields
    are non-null and plausible.
    """

    async def test_book_customers_each_get_a_snapshot(self, engine):
        """After seeding, every customer in the synthetic book has a snapshot."""
        from app.db.seed import _seed_kyc_baselines

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            await _seed_kyc_baselines(s)
            await s.commit()

        async with factory() as s:
            baselines = await load_all_baselines(s)

        book = generate_book()
        for customer in book:
            assert customer.drift_id in baselines, (
                f"No baseline seeded for {customer.drift_id} ({customer.name})"
            )

    async def test_seeded_snapshots_have_behavioral_baseline(self, engine):
        from app.db.seed import _seed_kyc_baselines

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            await _seed_kyc_baselines(s)
            await s.commit()

        async with factory() as s:
            baselines = await load_all_baselines(s)

        for cid, snap in baselines.items():
            assert snap.avg_monthly_volume_chf is not None, f"{cid}: missing volume baseline"
            assert snap.avg_monthly_volume_chf > 0, f"{cid}: non-positive volume baseline"
            # Counterparty and corridor risk should be between 0 and 1
            if snap.counterparty_risk_mean is not None:
                assert 0.0 <= snap.counterparty_risk_mean <= 1.0, cid
            if snap.corridor_risk_mean is not None:
                assert 0.0 <= snap.corridor_risk_mean <= 1.0, cid

    async def test_seeded_snapshot_type_is_seeded(self, engine):
        from app.db.seed import _seed_kyc_baselines

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            await _seed_kyc_baselines(s)
            await s.commit()

        async with factory() as s:
            result = await s.execute(select(EntitySnapshotDB))
            rows = list(result.scalars().all())

        assert all(r.snapshot_type == "seeded" for r in rows)
        assert all(r.source == "internal" for r in rows)

    async def test_stable_customer_baseline_uses_full_history(self, engine):
        """Stable customers have no drift window so baseline uses all months."""
        from app.db.seed import _seed_kyc_baselines

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            await _seed_kyc_baselines(s)
            await s.commit()

        async with factory() as s:
            result = await s.execute(select(EntitySnapshotDB))
            rows = list(result.scalars().all())

        # All stable customer snapshots must have a non-null volume baseline
        stable_rows = [r for r in rows if r.raw_data.get("scenario") == "stable"]
        assert stable_rows, "expected at least one stable customer snapshot"
        for row in stable_rows:
            assert row.avg_monthly_volume_chf is not None

    async def test_dormant_customer_has_low_baseline_volume(self, engine):
        """
        The dormancy_break customer's pre-drift baseline must be near-floor.
        seed uses months[:drift_start_month] so it captures the dormant window.
        """
        from app.db.seed import _seed_kyc_baselines

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            await _seed_kyc_baselines(s)
            await s.commit()

        async with factory() as s:
            result = await s.execute(select(EntitySnapshotDB))
            rows = list(result.scalars().all())

        dormant_rows = [r for r in rows if r.raw_data.get("scenario") == "dormancy_break"]
        assert dormant_rows, "expected a dormancy_break snapshot"
        for row in dormant_rows:
            # Dormant baseline ~ 150 CHF/day × 21 days ≈ 3 150; well below 5 000
            assert row.avg_monthly_volume_chf is not None
            assert row.avg_monthly_volume_chf < 5_000, (
                f"dormant baseline unexpectedly high: {row.avg_monthly_volume_chf}"
            )
