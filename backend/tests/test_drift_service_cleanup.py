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


async def test_timeline_is_available_only_on_canonical_subject_route(client):
    canonical_response = await client.get("/api/v1/drift/subjects/drift-001")
    removed_response = await client.get("/api/v1/drift/subjects/drift-001/timeline")

    assert canonical_response.status_code == 200
    assert canonical_response.json()["timeline"]
    # 404 specifically because no route matches (FastAPI's default body), not
    # because the old handler ran and reported an unknown subject.
    assert removed_response.status_code == 404
    assert removed_response.json() == {"detail": "Not Found"}
