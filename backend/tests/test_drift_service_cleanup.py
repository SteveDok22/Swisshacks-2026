"""Regression tests for the P2 drift-engine cleanups."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

import app.drift.service as drift_service
import app.drift.timetravel as timetravel
from app.core.config import (
    DRIFT_CONFIRMATION_LIFT_RANGE,
    DRIFT_CONFIRMATION_MAX_AMPLIFICATION,
    DRIFT_INTERNAL_ACCUMULATED_WEIGHT,
    DRIFT_INTERNAL_CONTAGION_WEIGHT,
    DRIFT_INTERNAL_VELOCITY_WEIGHT,
    DRIFT_PUBLIC_RISK_WEIGHT,
)
from app.drift.simulator import generate_customer


def test_drift_scoring_weights_keep_their_documented_values():
    """Guards against accidental drift of the published constant values.

    This only pins the values; the *wiring* tests below prove the call sites
    actually consume the constants rather than re-introducing magic numbers.
    """
    assert DRIFT_INTERNAL_VELOCITY_WEIGHT == 0.60
    assert DRIFT_INTERNAL_ACCUMULATED_WEIGHT == 0.25
    assert DRIFT_INTERNAL_CONTAGION_WEIGHT == 0.40
    assert DRIFT_PUBLIC_RISK_WEIGHT == 0.85
    assert DRIFT_CONFIRMATION_LIFT_RANGE == 3.0
    assert DRIFT_CONFIRMATION_MAX_AMPLIFICATION == 0.35


def test_get_drift_engine_warns_when_process_local_singleton_is_created(monkeypatch):
    engine = object()
    engine_factory = Mock(return_value=engine)
    warning = Mock()
    monkeypatch.setattr(drift_service, "_engine", None)
    monkeypatch.setattr(drift_service, "DriftEngine", engine_factory)
    monkeypatch.setattr(drift_service.logger, "warning", warning)

    first = drift_service.get_drift_engine()
    second = drift_service.get_drift_engine()

    assert first is engine
    assert second is engine
    engine_factory.assert_called_once_with()
    warning.assert_called_once_with(
        "drift_engine_single_worker_required",
        reason=(
            "DriftEngine uses process-local mutable state; configure exactly "
            "one API worker until state is moved to a shared store."
        ),
    )


# --- Constant wiring: prove the call sites actually consume the constants ---


def _replay_score(monkeypatch, *, month_t, prop_risk, listing_month, **overrides):
    """Replay one customer as-of ``month_t`` with the given constant overrides.

    Overrides are applied to the ``timetravel`` module namespace (the names the
    function resolves at call time), so a passing assertion proves the constant
    feeds the calculation rather than merely existing in ``config``.
    """
    cust = generate_customer("wiring", "Wiring Test", "combined", seed=42)
    for name, value in overrides.items():
        monkeypatch.setattr(timetravel, name, value)
    return timetravel.replay_as_of(
        cust,
        month_t,
        propagated_risk_final=prop_risk,
        contagion_listing_month=listing_month,
    ).as_of_score


@pytest.mark.parametrize(
    "constant",
    [
        "DRIFT_INTERNAL_VELOCITY_WEIGHT",
        "DRIFT_INTERNAL_ACCUMULATED_WEIGHT",
        "DRIFT_INTERNAL_CONTAGION_WEIGHT",
    ],
)
def test_internal_weights_are_wired_into_replay_scoring(monkeypatch, constant):
    """Zeroing any internal weight must lower an internal-risk-dominated score.

    At the final month with active contagion the internal layer saturates the
    fused score, so dropping each contributing weight to zero is observable.
    """
    baseline = _replay_score(
        monkeypatch, month_t=17, prop_risk=0.9, listing_month=0
    )
    with_zero = _replay_score(
        monkeypatch, month_t=17, prop_risk=0.9, listing_month=0, **{constant: 0.0}
    )
    assert with_zero < baseline


def test_public_risk_weight_is_wired_into_replay_scoring(monkeypatch):
    """When the public layer dominates, zeroing its weight lowers the score."""
    # Month 9 of the combined scenario: public risk leads, internal is still low.
    baseline = _replay_score(
        monkeypatch, month_t=9, prop_risk=0.0, listing_month=None
    )
    with_zero = _replay_score(
        monkeypatch,
        month_t=9,
        prop_risk=0.0,
        listing_month=None,
        DRIFT_PUBLIC_RISK_WEIGHT=0.0,
    )
    assert with_zero < baseline


def test_confirmation_amplification_consumes_both_constants():
    """The live engine's score amplification must read both confirmation
    constants (these are deliberately absent from the replay path).

    Asserting the exact arithmetic keeps this deterministic — drift scores
    depend on per-process signal seeds, so a relative live-engine comparison
    would be flaky and could be masked by the 100-point score cap.
    """
    # A lift of exactly 1 means the two worlds do not confirm each other:
    # no amplification, regardless of either constant.
    assert drift_service.confirmation_amplification(1.0) == pytest.approx(1.0)

    # A lift at the top of the window saturates at the full maximum, which
    # pins DRIFT_CONFIRMATION_MAX_AMPLIFICATION.
    saturating_lift = 1.0 + DRIFT_CONFIRMATION_LIFT_RANGE
    assert drift_service.confirmation_amplification(saturating_lift) == pytest.approx(
        1.0 + DRIFT_CONFIRMATION_MAX_AMPLIFICATION
    )

    # A lift halfway through the (unsaturated) window applies exactly half the
    # maximum — this pins BOTH constants independently: the window scales the
    # input, the maximum scales the output.
    half_window_lift = 1.0 + DRIFT_CONFIRMATION_LIFT_RANGE * 0.5
    assert drift_service.confirmation_amplification(half_window_lift) == pytest.approx(
        1.0 + 0.5 * DRIFT_CONFIRMATION_MAX_AMPLIFICATION
    )


# --- UC 1: news-spike month surfacing + confirmation-lift wiring ---


def _news_spike_analysis():
    """Run the shared analysis for a news_spike customer with its synthetic news."""
    from app.drift.public_intel import generate_signals_for_customer
    from app.drift.service import compute_drift_analysis
    from app.drift.stability import cohort_volatility

    cust = generate_customer("uc1", "Wirecard Holdings AG", "news_spike", seed=3)
    refs = [generate_customer(f"ref-{i}", "Ref", "stable", seed=900 + i) for i in range(8)]
    cohort_cv = cohort_volatility([c.monthly_volume for c in refs])
    signals = generate_signals_for_customer(
        cust.drift_id, cust.name, cust.scenario,
        months=cust.months, drift_start_month=cust.drift_start_month, seed=3,
    )
    return compute_drift_analysis(cust, cohort_cv=cohort_cv, public_signals=signals)


def test_news_spike_month_is_surfaced_in_analysis():
    """A sustained news spike surfaces a non-None news_spike_month (UC 1)."""
    analysis = _news_spike_analysis()
    assert analysis["news_spike_month"] is not None
    assert analysis["public_risk"] > 0.5


def test_news_spike_month_is_none_without_signals():
    """No public signals → no news spike month, neutral confirmation lift."""
    from app.drift.service import compute_drift_analysis

    cust = generate_customer("quiet", "Quiet AG", "stable", seed=1)
    analysis = compute_drift_analysis(cust, cohort_cv=0.2, public_signals=None)
    assert analysis["news_spike_month"] is None
    assert analysis["confirmation_lift"] == 1.0


def test_news_spike_month_anchors_confirmation_lift(monkeypatch):
    """The detected spike month — not the peak-severity month — must drive the
    confirmation-lift temporal window when a spike is present."""
    import app.drift.service as service

    captured: dict = {}

    def _spy(public_risk, internal_risk, public_peak, internal_peak, **kw):
        captured["public_peak"] = public_peak
        return 1.0

    monkeypatch.setattr(service, "detect_news_spike_month", lambda *a, **k: 7)
    monkeypatch.setattr(service, "confirmation_lift", _spy)

    _news_spike_analysis()
    assert captured["public_peak"] == 7


async def test_timeline_is_available_only_on_canonical_subject_route(client):
    canonical_response = await client.get("/api/v1/drift/subjects/drift-001")
    removed_response = await client.get("/api/v1/drift/subjects/drift-001/timeline")

    assert canonical_response.status_code == 200
    assert canonical_response.json()["timeline"]
    # 404 specifically because no route matches (FastAPI's default body), not
    # because the old handler ran and reported an unknown subject.
    assert removed_response.status_code == 404
    assert removed_response.json() == {"detail": "Not Found"}


# --- TTL cache tests for list_subjects() ---


def test_list_subjects_cache_hit_skips_reanalysis(monkeypatch):
    """Second call within TTL must return from cache without re-running analysis."""
    engine = drift_service.DriftEngine()
    call_count = 0
    original = engine._analyze_customer

    def counting_analyze(cust):
        nonlocal call_count
        call_count += 1
        return original(cust)

    monkeypatch.setattr(engine, "_analyze_customer", counting_analyze)

    first = engine.list_subjects()
    calls_after_first = call_count

    second = engine.list_subjects()

    assert second == first
    assert call_count == calls_after_first, (
        "list_subjects() re-ran _analyze_customer on a cache-hit call"
    )


def test_list_subjects_cache_returns_independent_list(monkeypatch):
    """Mutating the returned list must not corrupt subsequent cache hits."""
    engine = drift_service.DriftEngine()
    first = engine.list_subjects()
    original_len = len(first)

    # Mutate the returned list
    first.clear()

    second = engine.list_subjects()
    assert len(second) == original_len, (
        "Mutating the returned list corrupted the internal cache"
    )


def test_list_subjects_cache_expires_after_ttl(monkeypatch):
    """After TTL elapses, list_subjects() must re-run analysis."""
    engine = drift_service.DriftEngine()
    call_count = 0
    original = engine._analyze_customer

    def counting_analyze(cust):
        nonlocal call_count
        call_count += 1
        return original(cust)

    monkeypatch.setattr(engine, "_analyze_customer", counting_analyze)

    engine.list_subjects()
    calls_after_first = call_count

    # Force TTL expiry by pushing the cached timestamp into the past
    engine._list_cache_at -= engine._LIST_CACHE_TTL + 1.0

    engine.list_subjects()
    assert call_count > calls_after_first, (
        "list_subjects() served stale cache after TTL expiry"
    )
