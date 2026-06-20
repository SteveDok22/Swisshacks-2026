"""Hypothesis H1 — Changepoint detection leads the sanctions event.

    "Changepoint detection flags regime change months before the resulting
     sanctions event."  (README, Hypotheses and Validation)

Validation method: a synthetic scenario suite with known ground truth. We
inject a regime change (a step in transaction volume) at a known month and
place the simulated sanctions listing several months later. BOCPD must:

  1. detect the regime change,
  2. attribute it to the true step, not to a random earlier point (the
     detection EVENT is necessarily later — it needs a burn-in plus a
     confirmation window of post-step observations before it fires — so the
     attributed changepoint is the system's best estimate of WHERE the step
     happened, never a forecast of a step that has not yet occurred),
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
# Upper bound of the documented lead-time band (README: "2-7 month lead").
MAX_LEAD_MONTHS = 7
# One regime change per ~2 business years of daily data — the value the live
# engine uses in service.py.
HAZARD = 1.0 / 500.0
# BOCPD attributes a confirmed changepoint to the observation where the run
# reset; on a sharp step this lands within a day or two of the true step. This
# is an ATTRIBUTION offset, not look-ahead: the detection event itself fires
# later, after burn-in plus a confirmation window of post-step observations. We
# bound the back-dating tightly so the attributed point reflects the real step.
ATTRIBUTION_TOLERANCE_DAYS = 2
ACCURACY_TOLERANCE_DAYS = 10


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


def _detect_change_day(series: np.ndarray) -> int | None:
    """Run BOCPD and return the first detected changepoint as a day index."""
    result = BOCPD(hazard=HAZARD).run(standardize(series))
    if not result.detected_changepoints:
        return None
    return result.detected_changepoints[0]


def _day_to_month(day: int) -> int:
    """Map a day index to its nearest month. Rounding (not flooring) is the
    honest reading of "which month did the regime change land in": it cancels
    the <=1-day back-dating offset instead of letting it spill into the
    previous month."""
    return round(day / DAYS_PER_MONTH)


# Regime-change months chosen so the resulting lead times span the documented
# 2-7 month band against the fixed sanctions month.
CHANGE_MONTHS = [10, 11, 12, 13, 14, 15]
SEEDS = [0, 1, 2, 3, 4]


class TestH1LeadTime:
    @pytest.mark.parametrize("change_month", CHANGE_MONTHS)
    @pytest.mark.parametrize("seed", SEEDS)
    def test_changepoint_detected_with_sufficient_lead(self, change_month: int, seed: int):
        series = _step_volume_series(change_month, seed=seed)
        detected_day = _detect_change_day(series)
        change_day = change_month * DAYS_PER_MONTH

        assert detected_day is not None, f"BOCPD missed the regime change at month {change_month}"
        # Attribution is causal: the changepoint is attributed at most a day or
        # two before the true step (back-dating to the run reset), never a
        # forecast of a step that has not happened yet.
        assert detected_day >= change_day - ATTRIBUTION_TOLERANCE_DAYS, (
            f"detected day {detected_day} precedes true change day {change_day} "
            "by more than the back-dating tolerance — would imply a forecast"
        )
        # Accuracy: the changepoint lands on the true step, not somewhere random.
        assert abs(detected_day - change_day) <= ACCURACY_TOLERANCE_DAYS, (
            f"detected day {detected_day} is far from true change day {change_day}"
        )
        lead = SANCTIONS_MONTH - _day_to_month(detected_day)
        assert MIN_LEAD_MONTHS <= lead <= MAX_LEAD_MONTHS, (
            f"lead time {lead} outside documented {MIN_LEAD_MONTHS}-{MAX_LEAD_MONTHS} "
            f"month band (detected day {detected_day}, sanctions month {SANCTIONS_MONTH})"
        )

    def test_lead_time_distribution_matches_documented_band(self):
        leads = []
        for change_month in CHANGE_MONTHS:
            for seed in SEEDS:
                detected_day = _detect_change_day(_step_volume_series(change_month, seed=seed))
                assert detected_day is not None
                leads.append(SANCTIONS_MONTH - _day_to_month(detected_day))

        # The whole distribution sits inside the documented 2-7 month band, and
        # its median is a solid multi-month lead.
        assert min(leads) >= MIN_LEAD_MONTHS
        assert max(leads) <= MAX_LEAD_MONTHS
        assert MIN_LEAD_MONTHS <= np.median(leads) <= MAX_LEAD_MONTHS

    def test_simulator_step_scenario_is_detected(self):
        # dormancy_break is the suite's genuine step scenario (a dormant shell
        # that suddenly activates). BOCPD must flag it with positive lead.
        cust = generate_customer("step", "Dormant Shell", "dormancy_break", seed=7)
        result = BOCPD(hazard=HAZARD).run(standardize(cust.daily_volume_series()))
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
            result = BOCPD(hazard=HAZARD).run(standardize(cust.daily_volume_series()))
            assert result.detected_changepoints == [], (
                f"false positive on stable customer {cust.drift_id}: {result.detected_changepoints}"
            )

    @pytest.mark.parametrize("seed", range(42, 52))
    def test_stable_customers_across_seeds_have_zero_false_positives(self, seed: int):
        cust = generate_customer(f"stable-{seed}", "Control", "stable", seed=seed)
        result = BOCPD(hazard=HAZARD).run(standardize(cust.daily_volume_series()))
        assert result.detected_changepoints == [], (
            f"false positive on stable seed {seed}: {result.detected_changepoints}"
        )
