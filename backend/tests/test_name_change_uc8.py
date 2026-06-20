"""
UC8 — Legal entity name change → Re-KYC required.

Covers the three layers of the name-change feature end to end (offline, no
external APIs, no network):

1. Simulator — the `name_cycling` scenario exists, is risk-labelled, and pins
   the identity change to NAME_CHANGE_MONTH (the Mossack Fonseca shelf-cycling
   pattern).
2. Public-intel — the synthetic generator fires ZEFIX (`name_change`) and WHOIS
   (`domain_change`) signals at the change month.
3. Scoring policy — `_analyze_customer` records `name_changed` and floors the
   drift score at 60 on a confirmed name change, and `list_subjects` surfaces
   `is_name_changed` on the summary.

Run: pytest tests/test_name_change_uc8.py -v
"""

from __future__ import annotations

import pytest

import app.drift.service as _service
from app.drift.public_intel import generate_signals_for_customer
from app.drift.service import DriftEngine
from app.drift.simulator import (
    NAME_CHANGE_MONTH,
    SCENARIOS,
    generate_customer,
)

# Captured at import time, BEFORE conftest's autouse fixture patches the
# `_public_signals` seam to [] (it neutralises public-intel for the rest of the
# suite). The name-change feature is *driven* by public signals, so these tests
# restore the genuine method — which, with external_apis_enabled False (the
# default), runs the deterministic synthetic generator. No network, no keys.
_REAL_PUBLIC_SIGNALS = DriftEngine._public_signals


@pytest.fixture
def live_public_intel(monkeypatch):
    """Restore the real synthetic public-intel seam for name-change tests."""
    monkeypatch.setattr(_service.DriftEngine, "_public_signals", _REAL_PUBLIC_SIGNALS)


class TestNameCyclingScenario:
    def test_scenario_registered(self):
        assert "name_cycling" in SCENARIOS

    def test_name_cycling_is_risk_labelled(self):
        cust = generate_customer("uc8-1", "Meridian Trust Reg.", "name_cycling", seed=1)
        assert cust.causal_truth == "risk"

    def test_change_pinned_to_name_change_month(self):
        # The identity change is a fixed-month event regardless of the caller's
        # drift_start_month — both the demo book and the /inject path must agree.
        cust = generate_customer(
            "uc8-2", "Meridian Trust Reg.", "name_cycling",
            drift_start_month=12, seed=2,
        )
        assert cust.drift_start_month == NAME_CHANGE_MONTH

    def test_volume_stays_flat(self):
        # The identity change, not a volume surge, is the signal: the name_cycling
        # profile must not look like volume_creep / dormancy_break.
        cust = generate_customer("uc8-3", "Meridian Trust Reg.", "name_cycling", seed=3)
        first_mean = float(cust.monthly_volume[0].mean())
        last_mean = float(cust.monthly_volume[-1].mean())
        assert last_mean < first_mean * 1.5


class TestNameChangePublicSignals:
    def test_emits_zefix_and_whois_signals(self):
        signals = generate_signals_for_customer(
            "uc8-4", "Meridian Trust Reg.", "name_cycling",
            drift_start_month=NAME_CHANGE_MONTH, seed=4,
        )
        types = {s.signal_type for s in signals}
        assert "name_change" in types  # ZEFIX / GLEIF diff
        assert "domain_change" in types  # WHOIS registrant diff

    def test_signals_fire_at_change_month(self):
        signals = generate_signals_for_customer(
            "uc8-5", "Meridian Trust Reg.", "name_cycling",
            drift_start_month=NAME_CHANGE_MONTH, seed=5,
        )
        assert signals, "expected name_cycling to emit signals"
        assert all(s.month == NAME_CHANGE_MONTH for s in signals)

    def test_name_change_severity_is_high(self):
        signals = generate_signals_for_customer(
            "uc8-6", "Meridian Trust Reg.", "name_cycling",
            drift_start_month=NAME_CHANGE_MONTH, seed=6,
        )
        name_change = next(s for s in signals if s.signal_type == "name_change")
        assert name_change.severity >= 0.8

    def test_stable_emits_no_name_change(self):
        signals = generate_signals_for_customer("uc8-7", "Anna Keller", "stable", seed=7)
        assert all(s.signal_type != "name_change" for s in signals)


class TestNameChangeFloor:
    """The score floor is a regulatory invariant: a confirmed name change must
    surface for re-KYC regardless of how clean the transactions look."""

    def test_name_cycling_subject_is_floored_and_flagged(self, live_public_intel):
        engine = DriftEngine()
        engine._drift_model = None  # heuristic-only — keep the floor deterministic

        cust = next(c for c in engine._book if c.scenario == "name_cycling")
        analysis = engine._analyze_customer(cust)

        assert analysis["name_changed"] is True
        assert analysis["drift_score"] >= 60.0

    def test_stable_subject_not_flagged(self, live_public_intel):
        engine = DriftEngine()
        engine._drift_model = None

        cust = next(c for c in engine._book if c.scenario == "stable")
        analysis = engine._analyze_customer(cust)

        assert analysis["name_changed"] is False

    def test_summary_surfaces_is_name_changed(self, live_public_intel):
        engine = DriftEngine()
        summaries = engine.list_subjects()

        flagged = [s for s in summaries if s.is_name_changed]
        assert flagged, "expected at least one is_name_changed subject in the book"
        for s in flagged:
            # The floor must hold on the publicly surfaced score too.
            assert s.drift_score >= 60.0

    def test_detail_surfaces_is_name_changed(self, live_public_intel):
        # The flag must also be present on the full DriftSubjectDetail (UC8
        # follow-up), not just the summary, so the detail panel can render the
        # identity-reset treatment without re-deriving it from public_signals.
        engine = DriftEngine()
        engine._drift_model = None

        cust = next(c for c in engine._book if c.scenario == "name_cycling")
        detail = engine.get_subject(cust.drift_id)

        assert detail is not None
        assert detail.is_name_changed is True
        assert detail.drift_score >= 60.0
        # The underlying public signals that set the flag flow through the detail.
        signal_types = {s.signal_type for s in detail.public_signals}
        assert "name_change" in signal_types
        assert "domain_change" in signal_types

    def test_detail_not_flagged_for_stable(self, live_public_intel):
        engine = DriftEngine()
        engine._drift_model = None

        cust = next(c for c in engine._book if c.scenario == "stable")
        detail = engine.get_subject(cust.drift_id)

        assert detail is not None
        assert detail.is_name_changed is False


class TestNameChangeApiContract:
    """The `is_name_changed` flag must be present and correct on the public
    GET /drift/subjects response (the shape the frontend `name` badge reads)."""

    async def test_subjects_endpoint_exposes_is_name_changed(
        self, client, live_public_intel
    ):
        # The engine is a process singleton with a 30 s list cache; an earlier
        # test may have populated it under the stubbed ([]-signal) seam. Bust the
        # cache so this request recomputes under the restored live seam.
        _service.get_drift_engine()._list_cache = None

        resp = await client.get("/api/v1/drift/subjects")
        assert resp.status_code == 200

        subjects = resp.json()
        assert subjects, "expected a non-empty subject list"
        # Schema contract: every summary row carries the flag.
        assert all("is_name_changed" in s for s in subjects)
        # The demo book contains the name_cycling subject, so at least one fires.
        flagged = [s for s in subjects if s["is_name_changed"]]
        assert flagged, "expected at least one is_name_changed subject"
        assert all(s["drift_score"] >= 60.0 for s in flagged)

    async def test_detail_endpoint_exposes_is_name_changed(
        self, client, live_public_intel
    ):
        # The flag must also be on GET /drift/subjects/{id} (the shape the detail
        # panel reads), with the name_change/domain_change signals present.
        _service.get_drift_engine()._list_cache = None

        subjects = (await client.get("/api/v1/drift/subjects")).json()
        flagged = [s for s in subjects if s["is_name_changed"]]
        assert flagged, "expected at least one is_name_changed subject"

        resp = await client.get(f"/api/v1/drift/subjects/{flagged[0]['drift_id']}")
        assert resp.status_code == 200

        detail = resp.json()
        assert detail["is_name_changed"] is True
        assert detail["drift_score"] >= 60.0
        signal_types = {s["signal_type"] for s in detail["public_signals"]}
        assert "name_change" in signal_types
        assert "domain_change" in signal_types
