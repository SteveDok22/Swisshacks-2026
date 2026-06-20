"""Hypothesis H1 — Changepoint detection leads the sanctions event.

    "Changepoint detection flags regime change months before the resulting
     sanctions event."  (README, Hypotheses and Validation)

Validation method: a synthetic scenario suite with known ground truth. We
inject a regime change (a step in transaction volume) at a known month and
place the simulated sanctions listing several months later. BOCPD must:

  1. detect the regime change,
  2. detect it AT or AFTER the true change (it is an online/causal algorithm
     and cannot react before the change has happened),
  3. produce a lead time of at least two months before the listing,

and on the stable control group it must raise ZERO false positives.

BOCPD is the *regime-change* detector — it catches step shifts that threshold
rules miss. Gradual creep without a step is the velocity layer's job (H2); here
we test exactly what BOCPD is for: structural breaks.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.bocpd import BOCPD, standardize
from app.drift.simulator import generate_book, generate_customer

DAYS_PER_MONTH = 21
MONTHS = 18
SANCTIONS_MONTH = 17
MIN_LEAD_MONTHS = 2


def _step_volume_series(
    change_month: int,
    *,
    seed: int,
    low: float = 5_000.0,
    high: float = 11_000.0,
    noise_frac: float = 0.04,
) -> np.ndarray:
    """Daily volume series with a single regime change (step) at change_month."""
    rng = np.random.default_rng(seed)
    months = []
    for m in range(MONTHS):
        mean = high if m >= change_month else low
        months.append(rng.normal(mean, low * noise_frac, DAYS_PER_MONTH))
    return np.concatenate(months)


def _detect_change_month(series: np.ndarray) -> int | None:
    """Run BOCPD and map the first detected changepoint (a day index) to its
    month window."""
    result = BOCPD(hazard=1.0 / 500.0).run(standardize(series))
    if not result.detected_changepoints:
        return None
    return result.detected_changepoints[0] // DAYS_PER_MONTH


# Regime-change months spanning the realistic detection window. Each pairs with
# the fixed sanctions month to give a ground-truth lead time.
CHANGE_MONTHS = [6, 7, 8, 9, 10]
SEEDS = [0, 1, 2, 3, 4]


class TestH1LeadTime:
    @pytest.mark.parametrize("change_month", CHANGE_MONTHS)
    @pytest.mark.parametrize("seed", SEEDS)
    def test_changepoint_detected_with_sufficient_lead(self, change_month: int, seed: int):
        series = _step_volume_series(change_month, seed=seed)
        detected_month = _detect_change_month(series)

        assert detected_month is not None, f"BOCPD missed the regime change at month {change_month}"
        # Causal: detection cannot precede the change (allow the confirmation
        # delay of a few days that may straddle the month boundary).
        assert detected_month >= change_month - 1, (
            f"detected month {detected_month} precedes true change {change_month} "
            "— the detector cannot see the future"
        )
        lead = SANCTIONS_MONTH - detected_month
        assert lead >= MIN_LEAD_MONTHS, (
            f"lead time {lead} < required {MIN_LEAD_MONTHS} months "
            f"(detected month {detected_month}, sanctions month {SANCTIONS_MONTH})"
        )

    def test_lead_time_distribution_is_positive_with_documented_median(self):
        leads = []
        for change_month in CHANGE_MONTHS:
            for seed in SEEDS:
                detected = _detect_change_month(_step_volume_series(change_month, seed=seed))
                assert detected is not None
                leads.append(SANCTIONS_MONTH - detected)

        assert min(leads) >= MIN_LEAD_MONTHS
        assert np.median(leads) >= MIN_LEAD_MONTHS

    def test_simulator_step_scenario_is_detected(self):
        # dormancy_break is the suite's genuine step scenario (a dormant shell
        # that suddenly activates). BOCPD must flag it with positive lead.
        cust = generate_customer("step", "Dormant Shell", "dormancy_break", seed=7)
        result = BOCPD(hazard=1.0 / 500.0).run(standardize(cust.daily_volume_series()))
        assert result.detected_changepoints, "BOCPD missed the dormancy-break step"
        cp_month = cust.day_to_month(result.detected_changepoints[0])
        assert cust.sanctions_month is not None
        assert cust.sanctions_month - cp_month >= MIN_LEAD_MONTHS


class TestH1NoFalsePositives:
    def test_stable_book_has_zero_false_positives(self):
        book = generate_book()
        stable = [c for c in book if c.scenario == "stable"]
        assert stable, "demo book has no stable control group"
        for cust in stable:
            result = BOCPD(hazard=1.0 / 500.0).run(standardize(cust.daily_volume_series()))
            assert result.detected_changepoints == [], (
                f"false positive on stable customer {cust.drift_id}: {result.detected_changepoints}"
            )

    @pytest.mark.parametrize("seed", range(42, 52))
    def test_stable_customers_across_seeds_have_zero_false_positives(self, seed: int):
        cust = generate_customer(f"stable-{seed}", "Control", "stable", seed=seed)
        result = BOCPD(hazard=1.0 / 500.0).run(standardize(cust.daily_volume_series()))
        assert result.detected_changepoints == [], (
            f"false positive on stable seed {seed}: {result.detected_changepoints}"
        )
