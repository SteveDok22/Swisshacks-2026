"""Hypothesis H2 — Drift velocity leads; drift level lags.

    "Drift velocity is a leading indicator; drift level is lagging."
     (README, Hypotheses and Validation — validated via velocity vs
      absolute-threshold alerting.)

A bank's classic control is an absolute threshold on the monitored metric
("alert if monthly volume exceeds 2x the onboarding baseline"). It is set high
enough not to fire on normal fluctuation. The drift-velocity layer instead
watches the *rate* of structural change. The claim: at an EQUAL false-positive
rate (here, zero false positives on the stable control group), the velocity
detector fires strictly earlier than the absolute-threshold detector on
gradual-drift scenarios.

Both detectors are calibrated to zero false positives on the stable cohort, so
the comparison is at equal FP rate by construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.simulator import generate_book, generate_customer
from app.drift.velocity import compute_drift_series

# A "sane" absolute alert rule: monthly mean volume reaching 2x the onboarding
# baseline. High enough to never fire on the stable cohort.
BASELINE_VOLUME = 5_000.0
ABSOLUTE_THRESHOLD = 2.0 * BASELINE_VOLUME

# Gradual-drift scenarios whose volume ramps up over time.
GRADUAL_SCENARIOS = ["volume_creep", "combined"]
SEEDS = [0, 1, 2, 3, 4]


def _velocity_threshold_zero_fp(stable_customers) -> float:
    """Tightest velocity threshold with zero false positives on the stable
    cohort: just above the largest velocity any stable customer produces."""
    peak = 0.0
    for cust in stable_customers:
        ds = compute_drift_series(cust.metric_windows())
        if ds.velocity:
            peak = max(peak, max(ds.velocity))
    return peak * 1.05


def _velocity_alert_month(cust, threshold: float) -> int | None:
    ds = compute_drift_series(cust.metric_windows())
    return next(
        (ds.windows[i] for i, v in enumerate(ds.velocity) if v >= threshold),
        None,
    )


def _absolute_alert_month(cust, threshold: float) -> int | None:
    return next(
        (m for m in range(cust.months) if float(np.mean(cust.monthly_volume[m])) >= threshold),
        None,
    )


@pytest.fixture(scope="module")
def stable_cohort():
    return [c for c in generate_book() if c.scenario == "stable"]


@pytest.fixture(scope="module")
def velocity_threshold(stable_cohort) -> float:
    return _velocity_threshold_zero_fp(stable_cohort)


class TestH2EqualFalsePositiveRate:
    def test_both_detectors_have_zero_false_positives_on_stable(
        self, stable_cohort, velocity_threshold
    ):
        for cust in stable_cohort:
            assert _velocity_alert_month(cust, velocity_threshold) is None, (
                f"velocity false positive on stable customer {cust.drift_id}"
            )
            assert _absolute_alert_month(cust, ABSOLUTE_THRESHOLD) is None, (
                f"absolute-threshold false positive on stable customer {cust.drift_id}"
            )


class TestH2VelocityLeads:
    @pytest.mark.parametrize("scenario", GRADUAL_SCENARIOS)
    @pytest.mark.parametrize("seed", SEEDS)
    def test_velocity_alert_fires_before_absolute_alert(
        self, scenario: str, seed: int, velocity_threshold: float
    ):
        cust = generate_customer("h2", "Drifter", scenario, seed=seed)
        vel_month = _velocity_alert_month(cust, velocity_threshold)
        abs_month = _absolute_alert_month(cust, ABSOLUTE_THRESHOLD)

        assert vel_month is not None, "velocity detector never fired on a drift scenario"
        # The absolute detector may fire late or not at all within the horizon;
        # either way velocity must lead it.
        effective_abs_month = abs_month if abs_month is not None else cust.months
        assert vel_month < effective_abs_month, (
            f"velocity ({vel_month}) did not lead absolute threshold "
            f"({effective_abs_month}) for {scenario} seed {seed}"
        )

    def test_aggregate_lead_is_positive(self, velocity_threshold: float):
        leads = []
        for scenario in GRADUAL_SCENARIOS:
            for seed in SEEDS:
                cust = generate_customer("h2", "Drifter", scenario, seed=seed)
                vel_month = _velocity_alert_month(cust, velocity_threshold)
                abs_month = _absolute_alert_month(cust, ABSOLUTE_THRESHOLD)
                assert vel_month is not None
                effective_abs_month = abs_month if abs_month is not None else cust.months
                leads.append(effective_abs_month - vel_month)

        assert min(leads) > 0, "velocity failed to lead on at least one scenario"
        assert np.median(leads) >= 1
