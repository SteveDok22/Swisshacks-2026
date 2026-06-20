"""
Tests for the public-intelligence aggregator (gather_public_signals / _sync).

The aggregator dispatches fetch_signals() to all usable adapters and merges the
results. These tests verify:
  - all usable adapters are called
  - results are merged and time-sorted
  - one adapter failing does not prevent others from contributing
  - the sync bridge works correctly
  - the async function is safe to call directly in tests
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.drift.public_intel import (
    _AGGREGATE_TIMEOUT_S,
    _SYNC_TIMEOUT_S,
    assess_public_risk,
    classify_severity,
    gather_public_signals,
    gather_public_signals_sync,
    generate_signals_for_customer,
)

# Captured at import time, BEFORE the autouse fixture patches the seam to [] —
# lets the integration test below restore the genuine method.
from app.drift.service import DriftEngine as _DriftEngine
from app.sources.base import PublicSignal

_REAL_PUBLIC_SIGNALS = _DriftEngine._public_signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal(month: int, signal_type: str = "news", severity: float = 0.2) -> PublicSignal:
    return PublicSignal(
        month=month,
        signal_type=signal_type,
        headline=f"Test signal at month {month}",
        severity=severity,
        source="test_source",
        source_url="https://example.com/test",
    )


def _make_adapter_cls(
    source_name: str, signals: list[PublicSignal], raises: Exception | None = None
) -> MagicMock:
    """Return a fake adapter class whose fetch_signals returns the given signals."""
    mock_instance = MagicMock()
    mock_instance.source_name = source_name
    # Awaitable aclose so _safe_fetch's `await adapter.aclose()` is a real no-op
    # rather than awaiting a bare MagicMock (which raises TypeError, then gets
    # swallowed and logged — spurious noise that could mask an aclose regression).
    mock_instance.aclose = AsyncMock()

    if raises is not None:
        mock_instance.fetch_signals = AsyncMock(side_effect=raises)
    else:
        mock_instance.fetch_signals = AsyncMock(return_value=signals)

    cls = MagicMock()
    cls.source_name = source_name
    cls.return_value = mock_instance
    return cls


# ---------------------------------------------------------------------------
# gather_public_signals — async
# ---------------------------------------------------------------------------

class TestGatherPublicSignals:
    async def test_aggregates_signals_from_all_adapters(self):
        cls_a = _make_adapter_cls("a", [_signal(5), _signal(10)])
        cls_b = _make_adapter_cls("b", [_signal(3)])

        with patch("app.sources.registry.usable_adapters", return_value=(cls_a, cls_b)):
            signals = await gather_public_signals("drift-001", "Acme AG")

        assert len(signals) == 3
        assert [s.month for s in signals] == [3, 5, 10]

    async def test_returns_empty_when_all_adapters_return_empty(self):
        cls_a = _make_adapter_cls("a", [])
        cls_b = _make_adapter_cls("b", [])

        with patch("app.sources.registry.usable_adapters", return_value=(cls_a, cls_b)):
            signals = await gather_public_signals("drift-001", "Quiet AG")

        assert signals == []

    async def test_failing_adapter_does_not_block_others(self):
        cls_ok = _make_adapter_cls("ok", [_signal(7)])
        cls_bad = _make_adapter_cls("bad", [], raises=RuntimeError("network failure"))

        with patch("app.sources.registry.usable_adapters", return_value=(cls_ok, cls_bad)):
            signals = await gather_public_signals("drift-001", "Resilient AG")

        assert len(signals) == 1
        assert signals[0].source == "test_source"

    async def test_output_is_time_sorted(self):
        cls_a = _make_adapter_cls("a", [_signal(12), _signal(2)])
        cls_b = _make_adapter_cls("b", [_signal(7)])

        with patch("app.sources.registry.usable_adapters", return_value=(cls_a, cls_b)):
            signals = await gather_public_signals("drift-001", "Order AG")

        assert [s.month for s in signals] == [2, 7, 12]

    async def test_kwargs_passed_through_to_adapters(self):
        captured_kwargs: dict = {}

        async def capturing_fetch(drift_id, name, **kwargs):
            captured_kwargs.update(kwargs)
            return []

        mock_instance = MagicMock()
        mock_instance.source_name = "capturing"
        mock_instance.fetch_signals = capturing_fetch
        cls = MagicMock()
        cls.source_name = "capturing"
        cls.return_value = mock_instance

        with patch("app.sources.registry.usable_adapters", return_value=(cls,)):
            await gather_public_signals("drift-001", "AG", since_month=3, domain="example.com")

        assert captured_kwargs.get("since_month") == 3
        assert captured_kwargs.get("domain") == "example.com"

    async def test_aclose_called_on_adapter_with_that_method(self):
        aclose_mock = AsyncMock()
        mock_instance = MagicMock()
        mock_instance.source_name = "closable"
        mock_instance.fetch_signals = AsyncMock(return_value=[])
        mock_instance.aclose = aclose_mock
        cls = MagicMock()
        cls.source_name = "closable"
        cls.return_value = mock_instance

        with patch("app.sources.registry.usable_adapters", return_value=(cls,)):
            await gather_public_signals("drift-001", "AG")

        aclose_mock.assert_called_once()

    async def test_aclose_called_even_when_fetch_raises(self):
        aclose_mock = AsyncMock()
        mock_instance = MagicMock()
        mock_instance.source_name = "closable_bad"
        mock_instance.fetch_signals = AsyncMock(side_effect=RuntimeError("boom"))
        mock_instance.aclose = aclose_mock
        cls = MagicMock()
        cls.source_name = "closable_bad"
        cls.return_value = mock_instance

        with patch("app.sources.registry.usable_adapters", return_value=(cls,)):
            signals = await gather_public_signals("drift-001", "AG")

        assert signals == []
        aclose_mock.assert_called_once()

    async def test_adapter_without_aclose_does_not_raise(self):
        mock_instance = MagicMock(spec=["source_name", "fetch_signals"])
        mock_instance.source_name = "no_close"
        mock_instance.fetch_signals = AsyncMock(return_value=[_signal(1)])
        cls = MagicMock()
        cls.source_name = "no_close"
        cls.return_value = mock_instance

        with patch("app.sources.registry.usable_adapters", return_value=(cls,)):
            signals = await gather_public_signals("drift-001", "AG")

        assert len(signals) == 1

    async def test_multiple_failing_adapters_all_isolated(self):
        errors = [RuntimeError("a"), ValueError("b"), TimeoutError("c")]
        bad_classes = [
            _make_adapter_cls(f"bad_{i}", [], raises=err)
            for i, err in enumerate(errors)
        ]
        cls_ok = _make_adapter_cls("ok", [_signal(5)])

        with patch("app.sources.registry.usable_adapters", return_value=(*bad_classes, cls_ok)):
            signals = await gather_public_signals("drift-001", "AG")

        assert len(signals) == 1

    async def test_aggregate_timeout_returns_empty(self, monkeypatch):
        async def slow_fetch(drift_id, name, **kw):
            await asyncio.sleep(1000)
            return []

        mock_instance = MagicMock()
        mock_instance.source_name = "slow"
        mock_instance.fetch_signals = slow_fetch
        cls = MagicMock()
        cls.source_name = "slow"
        cls.return_value = mock_instance

        monkeypatch.setattr("app.drift.public_intel._AGGREGATE_TIMEOUT_S", 0.05)
        with patch("app.sources.registry.usable_adapters", return_value=(cls,)):
            signals = await gather_public_signals("drift-001", "AG")

        assert signals == []

    async def test_no_usable_adapters_returns_empty(self):
        with patch("app.sources.registry.usable_adapters", return_value=()):
            signals = await gather_public_signals("drift-001", "AG")

        assert signals == []

    async def test_slow_adapter_dropped_but_others_survive(self, monkeypatch):
        # Per-adapter timeout isolates the slow source: it returns [] on its own
        # while the fast adapter's results still make it through (partial, not
        # all-or-nothing, degradation).
        async def slow_fetch(drift_id, name, **kw):
            await asyncio.sleep(1000)
            return [_signal(99)]

        slow_instance = MagicMock()
        slow_instance.source_name = "slow"
        slow_instance.fetch_signals = slow_fetch
        cls_slow = MagicMock()
        cls_slow.source_name = "slow"
        cls_slow.return_value = slow_instance

        cls_fast = _make_adapter_cls("fast", [_signal(5)])

        monkeypatch.setattr("app.drift.public_intel._PER_ADAPTER_TIMEOUT_S", 0.05)
        with patch("app.sources.registry.usable_adapters", return_value=(cls_slow, cls_fast)):
            signals = await gather_public_signals("drift-001", "AG")

        assert [s.month for s in signals] == [5]

    async def test_adapter_construction_error_isolated(self):
        # An adapter whose __init__ raises must not sink the whole aggregation.
        cls_bad = MagicMock(side_effect=RuntimeError("init boom"))
        cls_bad.source_name = "bad_init"
        cls_ok = _make_adapter_cls("ok", [_signal(3)])

        with patch("app.sources.registry.usable_adapters", return_value=(cls_bad, cls_ok)):
            signals = await gather_public_signals("drift-001", "AG")

        assert [s.month for s in signals] == [3]

    def test_timeout_constants_are_sane(self):
        assert _AGGREGATE_TIMEOUT_S > 0
        assert _SYNC_TIMEOUT_S > _AGGREGATE_TIMEOUT_S


# ---------------------------------------------------------------------------
# gather_public_signals_sync — thread-based bridge
# ---------------------------------------------------------------------------

class TestGatherPublicSignalsSync:
    def test_sync_returns_same_result_as_async(self):
        cls_a = _make_adapter_cls("a", [_signal(4), _signal(9)])

        with patch("app.sources.registry.usable_adapters", return_value=(cls_a,)):
            result = gather_public_signals_sync("drift-001", "Sync AG")

        assert len(result) == 2
        assert result[0].month == 4
        assert result[1].month == 9

    def test_sync_returns_empty_on_all_errors(self):
        cls_bad = _make_adapter_cls("bad", [], raises=RuntimeError("fail"))

        with patch("app.sources.registry.usable_adapters", return_value=(cls_bad,)):
            result = gather_public_signals_sync("drift-001", "AG")

        assert result == []

    def test_sync_bridge_safe_when_called_repeatedly(self):
        signals = [_signal(1), _signal(2)]
        cls_a = _make_adapter_cls("a", signals)

        with patch("app.sources.registry.usable_adapters", return_value=(cls_a,)):
            r1 = gather_public_signals_sync("d1", "AG1")
            r2 = gather_public_signals_sync("d2", "AG2")

        assert len(r1) == 2
        assert len(r2) == 2

    def test_sync_result_is_sorted(self):
        cls_a = _make_adapter_cls("a", [_signal(10), _signal(1), _signal(5)])

        with patch("app.sources.registry.usable_adapters", return_value=(cls_a,)):
            result = gather_public_signals_sync("drift-001", "AG")

        assert [s.month for s in result] == [1, 5, 10]

    def test_sync_bridge_timeout_returns_empty(self, monkeypatch):
        # The sync ceiling is the safety valve: if the worker overruns it, the
        # bridge must return [] rather than block the caller. Keep the per-adapter
        # cap above the sync ceiling so the sync timeout is what fires, but keep
        # the aggregate cap just below it so the worker's event loop is cancelled
        # cleanly (no abandoned asyncio.sleep left running in a daemon thread).
        async def slow_fetch(drift_id, name, **kw):
            await asyncio.sleep(5)
            return []

        mock_instance = MagicMock()
        mock_instance.source_name = "slow"
        mock_instance.aclose = AsyncMock()
        mock_instance.fetch_signals = slow_fetch
        cls = MagicMock()
        cls.source_name = "slow"
        cls.return_value = mock_instance

        monkeypatch.setattr("app.drift.public_intel._PER_ADAPTER_TIMEOUT_S", 1000.0)
        monkeypatch.setattr("app.drift.public_intel._AGGREGATE_TIMEOUT_S", 0.2)
        monkeypatch.setattr("app.drift.public_intel._SYNC_TIMEOUT_S", 0.05)
        with patch("app.sources.registry.usable_adapters", return_value=(cls,)):
            result = gather_public_signals_sync("drift-001", "AG")

        assert result == []


# ---------------------------------------------------------------------------
# Regression — generate_signals_for_customer() still works for replay/tests
# ---------------------------------------------------------------------------

class TestSyntheticSignalsRegression:
    def test_stable_customer_returns_sorted_signals(self):
        signals = generate_signals_for_customer("d", "Alice", "stable", seed=42)
        months = [s.month for s in signals]
        assert months == sorted(months)

    def test_drifting_customer_has_escalating_severity(self):
        signals = generate_signals_for_customer("d", "Bob", "velocity", drift_start_month=5, seed=42)
        assert len(signals) >= 1
        assert any(s.severity > 0.5 for s in signals)

    def test_combined_adds_sanctions_signal(self):
        signals = generate_signals_for_customer(
            "d", "Carol", "combined", months=20, drift_start_month=4, seed=42
        )
        types = {s.signal_type for s in signals}
        assert "sanctions" in types

    def test_classify_severity_lexicon_matches(self):
        assert classify_severity("money laundering investigation") > 0.8
        assert classify_severity("new hiring in Zurich") < 0.3

    def test_assess_public_risk_empty_signals(self):
        result = assess_public_risk([])
        assert result.public_risk == 0.0
        assert result.peak_signal_month is None

    def test_assess_public_risk_multiple_high_severity(self):
        signals = [
            _signal(3, "sanctions", 0.9),
            _signal(5, "adverse_media", 0.85),
            _signal(7, "adverse_media", 0.8),
        ]
        result = assess_public_risk(signals)
        assert result.public_risk > 0.7
        assert result.peak_signal_month == 3


# ---------------------------------------------------------------------------
# Integration — with external APIs ENABLED, DriftEngine flows real adapter
# signals through the sync bridge. The autouse conftest fixture stubs the
# _public_signals seam to [] for every other test, so this is the ONE place the
# engine<->aggregator wiring (the whole point of the PR) is exercised end-to-end.
# It restores the real seam and flips the master switch on.
# ---------------------------------------------------------------------------

class TestEngineAggregatorWiring:
    def test_analyze_customer_consumes_real_aggregator_signals(self, monkeypatch):
        from app.drift import service

        # Restore the genuine seam (autouse stub replaced it) and enable live mode
        # so the engine routes through the real sync bridge + aggregator.
        monkeypatch.setattr(service.DriftEngine, "_public_signals", _REAL_PUBLIC_SIGNALS)
        monkeypatch.setattr(service.settings, "external_apis_enabled", True)
        cls = _make_adapter_cls("adverse", [_signal(5, "adverse_media", 0.9)])
        monkeypatch.setattr("app.sources.registry.usable_adapters", lambda: (cls,))

        engine = service.DriftEngine()
        analysis = engine._analyze_customer(engine._book[0])

        assert [s.severity for s in analysis["public_signals"]] == [0.9]
        assert analysis["public_risk"] > 0.0

    def test_offline_mode_uses_synthetic_signals_no_adapters(self, monkeypatch):
        # With the master switch OFF (default), the engine must NOT touch the
        # adapter registry at all — usable_adapters() raises if called — and must
        # still produce mocked (synthetic) public signals.
        from app.drift import service
        from app.drift.simulator import generate_customer

        monkeypatch.setattr(service.DriftEngine, "_public_signals", _REAL_PUBLIC_SIGNALS)
        monkeypatch.setattr(service.settings, "external_apis_enabled", False)

        def _boom():
            raise AssertionError("usable_adapters() must not be called offline")

        monkeypatch.setattr("app.sources.registry.usable_adapters", _boom)

        engine = service.DriftEngine()
        # A drifting customer yields scenario-aligned synthetic signals offline.
        cust = generate_customer(
            drift_id="drift-offline", name="Drifty AG",
            scenario="volume_creep", drift_start_month=4, seed=1,
        )
        analysis = engine._analyze_customer(cust)

        assert analysis["public_signals"], "offline synthetic path should emit signals"
