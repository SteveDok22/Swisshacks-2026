"""
Tests for the LIVE website-text wiring of the business-model comparator
(``DriftEngine._business_model_comparison`` and its live helpers).

These close the PR #44 follow-ups: in live mode the two website texts are sourced
from the Wayback (onboarding) and Firecrawl (current) adapters, fed through the
pure comparator, and the comparator's embeddings are persisted to — and re-read
from — ``EntitySnapshotDB.raw_data`` as a read-through cache.

Everything here runs fully offline: no live tokens, no network. The Wayback /
Firecrawl adapters are replaced with in-memory fakes, the embeddings backend is a
deterministic injected fake (matching ``tests/test_business_model.py``), and the
DB is an in-memory SQLite engine awaited in the test's own event loop (so the
async helpers are exercised directly, with no cross-loop bridge).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select

import app.db.kyc_baseline  # noqa: F401 — register entity_snapshots table
import app.drift.business_model as bm
import app.drift.service as service
from app.db.kyc_baseline import EntitySnapshotDB
from app.drift.business_model import (
    BUSINESS_MODEL_DISTANCE_THRESHOLD,
    WEBSITE_COMPARISON_SOURCE,
    BusinessModelComparison,
)
from app.sources.base import EntitySnapshot, PublicSignal

# Both texts clear the comparator's 50-char floor; orthogonal embeddings → a
# cosine distance of 1.0, comfortably above the change threshold.
_ONBOARDING = "Helvetia Trading AG is a boutique import and export consultancy based in Zug."
_CURRENT = "HelvetiaX is a regulated cryptocurrency exchange offering token swaps and custody."
_DOMAIN = "helvetia.example"
_DRIFT_ID = "drift-009"
_NAME = "Helvetia Trading AG"


# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #
class _CountingEmbedder:
    """Deterministic embedder mapping known (stripped) texts → fixed vectors.

    Records every ``encode`` call so a test can prove a cache hit skips embedding.
    """

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping
        self.encoded: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.encoded.append(list(texts))
        return np.array([self._mapping[t] for t in texts], dtype=float)


def _orthogonal_embedder() -> _CountingEmbedder:
    return _CountingEmbedder({_ONBOARDING: [1.0, 0.0, 0.0], _CURRENT: [0.0, 1.0, 0.0]})


class _FakeWayback:
    """Stand-in WaybackAdapter: returns a canned onboarding snapshot."""

    def __init__(self, text: str | None = _ONBOARDING, *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.fetch_calls: list[dict] = []

    async def fetch(self, drift_id: str, name: str, **kwargs: object) -> EntitySnapshot | None:
        self.fetch_calls.append(dict(kwargs))
        if self._raises:
            raise RuntimeError("wayback boom")
        if self._text is None:
            return None
        return EntitySnapshot(
            drift_id=drift_id, name=name, source="wayback",
            raw_data={"website_text": self._text},
        )

    async def aclose(self) -> None:
        return None


class _FakeFirecrawl:
    """Stand-in FirecrawlAdapter: returns a canned current snapshot + URL."""

    def __init__(self, text: str | None = _CURRENT, *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises
        self.fetch_calls: list[dict] = []

    async def fetch(self, drift_id: str, name: str, **kwargs: object) -> EntitySnapshot | None:
        self.fetch_calls.append(dict(kwargs))
        if self._raises:
            raise RuntimeError("firecrawl boom")
        return EntitySnapshot(
            drift_id=drift_id, name=name, source="firecrawl",
            raw_data={"website_text": self._text, "url": f"https://{_DOMAIN}"},
        )

    async def aclose(self) -> None:
        return None


# --------------------------------------------------------------------------- #
# In-memory DB wired into service.session_scope                               #
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def live_db(monkeypatch):
    """Fresh in-memory SQLite + a session_scope patched onto the service module.

    StaticPool keeps one underlying connection so committed rows are visible to
    every session. The helpers are awaited in this same loop, so the engine is
    only ever used from one event loop (no cross-loop bridge in these tests).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    @asynccontextmanager
    async def _scope():
        async with factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    monkeypatch.setattr(service, "session_scope", _scope)
    yield factory
    await engine.dispose()


async def _seed_domain(
    factory, *, domain: str | None = _DOMAIN, embeddings: dict | None = None
) -> None:
    """Insert a baseline snapshot carrying ``domain`` (and optional cached embeddings)."""
    raw: dict = {}
    if domain is not None:
        raw["domain"] = domain
    if embeddings is not None:
        raw[service._BUSINESS_MODEL_EMBEDDINGS_KEY] = embeddings
    async with factory() as s:
        s.add(
            EntitySnapshotDB(
                drift_id=_DRIFT_ID,
                snapshot_date=date(2023, 1, 1),
                snapshot_type="seeded",
                source="internal",
                name=_NAME,
                raw_data=raw,
            )
        )
        await s.commit()


async def _firecrawl_rows(factory) -> list[EntitySnapshotDB]:
    async with factory() as s:
        result = await s.execute(
            select(EntitySnapshotDB).where(EntitySnapshotDB.source == "firecrawl")
        )
        return list(result.scalars().all())


@pytest.fixture
def offline_engine() -> service.DriftEngine:
    """A DriftEngine built in the default offline mode (no live GLEIF fetch)."""
    return service.DriftEngine()


# --------------------------------------------------------------------------- #
# (a) Live sourcing → business_model_change signal                            #
# --------------------------------------------------------------------------- #
class TestLiveSourcing:
    async def test_sources_texts_from_adapters_and_emits_signal(
        self, live_db, offline_engine, monkeypatch
    ):
        await _seed_domain(live_db)
        wayback = _FakeWayback()
        firecrawl = _FakeFirecrawl()
        monkeypatch.setattr(service, "WaybackAdapter", lambda: wayback)
        monkeypatch.setattr(service, "FirecrawlAdapter", lambda: firecrawl)
        monkeypatch.setattr(bm, "_get_default_embedder", lambda: _orthogonal_embedder())

        result = await offline_engine._gather_business_model_async(
            _DRIFT_ID, _NAME, month=8
        )

        assert result is not None
        assert result.is_change is True
        assert result.signal is not None
        assert result.signal.signal_type == "business_model_change"
        assert result.signal.month == 8
        assert result.signal.source == WEBSITE_COMPARISON_SOURCE
        assert result.signal.source_url == f"https://{_DOMAIN}"
        # The persisted domain reached the Wayback adapter (no name-slug guess).
        assert wayback.fetch_calls[0]["domain"] == _DOMAIN
        assert firecrawl.fetch_calls[0]["domain"] == _DOMAIN


# --------------------------------------------------------------------------- #
# (b) Embedding persistence + read-through reuse on re-scan                    #
# --------------------------------------------------------------------------- #
class TestEmbeddingPersistence:
    async def test_embeddings_persisted_then_reused_on_rescan(
        self, live_db, offline_engine, monkeypatch
    ):
        await _seed_domain(live_db)
        embedder = _orthogonal_embedder()
        monkeypatch.setattr(service, "WaybackAdapter", lambda: _FakeWayback())
        monkeypatch.setattr(service, "FirecrawlAdapter", lambda: _FakeFirecrawl())
        monkeypatch.setattr(bm, "_get_default_embedder", lambda: embedder)

        # First scan: both sides embedded (one encode call each) and persisted.
        first = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=8)
        assert first is not None and first.is_change is True
        assert len(embedder.encoded) == 2  # wayback + current

        rows = await _firecrawl_rows(live_db)
        assert len(rows) == 1
        stored = rows[0].raw_data[service._BUSINESS_MODEL_EMBEDDINGS_KEY]
        assert first.wayback_embedding.fingerprint in stored
        assert first.current_embedding.fingerprint in stored
        assert stored[first.wayback_embedding.fingerprint] == [1.0, 0.0, 0.0]

        # Second scan: same texts → both fingerprints hit the persisted cache, so
        # the embedder is NOT called again and no new snapshot row is written.
        second = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=8)
        assert second is not None and second.is_change is True
        assert len(embedder.encoded) == 2, "re-scan must not re-embed unchanged text"
        assert len(await _firecrawl_rows(live_db)) == 1, "unchanged scan must not append a row"


# --------------------------------------------------------------------------- #
# (c) Graceful degradation                                                     #
# --------------------------------------------------------------------------- #
class TestGracefulDegradation:
    async def test_no_domain_returns_none_without_touching_adapters(
        self, live_db, offline_engine, monkeypatch
    ):
        await _seed_domain(live_db, domain=None)  # baseline with no domain
        wayback = _FakeWayback()
        firecrawl = _FakeFirecrawl()
        monkeypatch.setattr(service, "WaybackAdapter", lambda: wayback)
        monkeypatch.setattr(service, "FirecrawlAdapter", lambda: firecrawl)

        result = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=0)

        assert result is None
        assert wayback.fetch_calls == []
        assert firecrawl.fetch_calls == []

    async def test_no_persisted_baseline_returns_none(
        self, live_db, offline_engine, monkeypatch
    ):
        # Nothing seeded at all → no domain → inert.
        monkeypatch.setattr(service, "WaybackAdapter", lambda: _FakeWayback())
        monkeypatch.setattr(service, "FirecrawlAdapter", lambda: _FakeFirecrawl())
        result = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=0)
        assert result is None

    async def test_adapter_error_degrades_to_skip_no_signal(
        self, live_db, offline_engine, monkeypatch
    ):
        await _seed_domain(live_db)
        # Wayback raises → no onboarding text → comparator skips (empty_text),
        # emits no signal, and persists nothing.
        monkeypatch.setattr(service, "WaybackAdapter", lambda: _FakeWayback(raises=True))
        monkeypatch.setattr(service, "FirecrawlAdapter", lambda: _FakeFirecrawl())
        monkeypatch.setattr(bm, "_get_default_embedder", lambda: _orthogonal_embedder())

        result = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=8)

        assert result is not None
        assert result.skipped is True
        assert result.signal is None
        assert await _firecrawl_rows(live_db) == []

    async def test_no_embedder_degrades_to_skip(
        self, live_db, offline_engine, monkeypatch
    ):
        await _seed_domain(live_db)
        monkeypatch.setattr(service, "WaybackAdapter", lambda: _FakeWayback())
        monkeypatch.setattr(service, "FirecrawlAdapter", lambda: _FakeFirecrawl())
        # model2vec absent and none injected → comparator returns no_embedder skip.
        monkeypatch.setattr(bm, "_get_default_embedder", lambda: None)

        result = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=8)

        assert result is not None
        assert result.skipped_reason == "no_embedder"
        assert result.signal is None
        assert await _firecrawl_rows(live_db) == []

    async def test_db_unavailable_degrades_to_none(self, offline_engine, monkeypatch):
        # session_scope raises (DB down) → baseline load fails → inert, no crash.
        @asynccontextmanager
        async def _boom():
            raise RuntimeError("db down")
            yield  # pragma: no cover

        monkeypatch.setattr(service, "session_scope", _boom)
        result = await offline_engine._gather_business_model_async(_DRIFT_ID, _NAME, month=0)
        assert result is None


# --------------------------------------------------------------------------- #
# Offline inertness — the default path must not touch adapters or the DB       #
# --------------------------------------------------------------------------- #
class TestOfflineInertness:
    def test_offline_path_ignores_adapters_and_db(self, offline_engine, monkeypatch):
        from app.drift.simulator import generate_customer

        def _boom(*_a, **_k):
            raise AssertionError("offline path must not construct live adapters / DB")

        monkeypatch.setattr(service, "WaybackAdapter", _boom)
        monkeypatch.setattr(service, "FirecrawlAdapter", _boom)
        monkeypatch.setattr(service, "session_scope", _boom)
        # external_apis_enabled is False by default → synthetic path only.
        cust = generate_customer("drift-stable", "Control AG", "stable", seed=2)
        assert offline_engine._business_model_comparison(cust) is None


# --------------------------------------------------------------------------- #
# Live routing + fold into the public layer + sync-bridge wrapper             #
# --------------------------------------------------------------------------- #
class TestLiveRoutingAndBridge:
    def test_live_flag_routes_to_live_comparison(self, offline_engine, monkeypatch):
        from app.drift.simulator import generate_customer

        captured: dict = {}

        def _fake_live(cust):
            captured["cust"] = cust
            return None

        monkeypatch.setattr(service.settings, "external_apis_enabled", True)
        monkeypatch.setattr(offline_engine, "_live_business_model_comparison", _fake_live)
        cust = generate_customer("drift-x", "X AG", "stable", seed=1)
        offline_engine._business_model_comparison(cust)
        assert captured["cust"] is cust

    def test_live_signal_folds_into_public_layer(self, offline_engine, monkeypatch):
        from app.drift.simulator import generate_customer

        signal = PublicSignal(
            month=8, signal_type="business_model_change",
            headline="Website content shifted materially since onboarding",
            severity=0.9, source=WEBSITE_COMPARISON_SOURCE,
            source_url="https://example.com/site",
        )
        comparison = BusinessModelComparison(
            drift_id="drift-x", name="X AG", distance=0.52, is_change=True, signal=signal,
        )
        monkeypatch.setattr(service.settings, "external_apis_enabled", True)
        monkeypatch.setattr(
            offline_engine, "_live_business_model_comparison", lambda cust: comparison
        )
        cust = generate_customer("drift-x", "X AG", "stable", seed=1)
        analysis = offline_engine._analyze_customer(cust)

        assert analysis["is_business_model_change"] is True
        assert analysis["business_model_distance"] == pytest.approx(0.52)
        assert any(
            s.signal_type == "business_model_change" for s in analysis["public_signals"]
        )

    def test_sync_bridge_returns_comparison(self, offline_engine, monkeypatch):
        from app.drift.simulator import generate_customer

        comparison = BusinessModelComparison(
            drift_id="d", name="N", distance=0.4, is_change=True, signal=None,
        )

        async def _fake_async(drift_id, name, *, month):
            return comparison

        monkeypatch.setattr(offline_engine, "_gather_business_model_async", _fake_async)
        cust = generate_customer("drift-x", "X AG", "stable", seed=1)
        assert offline_engine._live_business_model_comparison(cust) is comparison

    def test_sync_bridge_degrades_on_error(self, offline_engine, monkeypatch):
        from app.drift.simulator import generate_customer

        async def _boom(drift_id, name, *, month):
            raise RuntimeError("worker boom")

        monkeypatch.setattr(offline_engine, "_gather_business_model_async", _boom)
        cust = generate_customer("drift-x", "X AG", "stable", seed=1)
        assert offline_engine._live_business_model_comparison(cust) is None


# --------------------------------------------------------------------------- #
# Constant sanity                                                             #
# --------------------------------------------------------------------------- #
def test_change_threshold_constant_is_referenced():
    # Guards against an accidental drift in the comparator's public threshold the
    # live wiring relies on (a website signal's mere presence means distance ≥ it).
    assert BUSINESS_MODEL_DISTANCE_THRESHOLD == 0.35
