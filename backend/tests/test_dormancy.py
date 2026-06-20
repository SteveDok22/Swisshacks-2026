"""Unit tests for the dormancy-break (suspicious activation) detector."""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.dormancy import DormancyResult, assess_dormancy
from app.drift.simulator import generate_book, generate_customer


def _dormant_then_active(
    months: int = 18,
    dormant_months: int = 9,
    dormant_level: float = 50.0,
    active_level: float = 8000.0,
) -> list:
    """A near-zero baseline that suddenly surges to high volume."""
    rng = np.random.default_rng(42)
    out = []
    for m in range(months):
        if m < dormant_months:
            out.append(rng.normal(dormant_level, dormant_level * 0.2, 21).clip(0))
        else:
            out.append(rng.normal(active_level, active_level * 0.06, 21).clip(0))
    return out


def _steady(months: int = 18, level: float = 5000.0) -> list:
    """Always-active, steady volume — no dormancy."""
    rng = np.random.default_rng(1)
    return [rng.normal(level, level * 0.15, 21).clip(0) for _ in range(months)]


def _growing(months: int = 18, start: float = 3000.0, step: float = 400.0) -> list:
    """Always-active but growing — ordinary drift, NOT a dormancy break."""
    rng = np.random.default_rng(2)
    return [rng.normal(start + m * step, 500, 21).clip(0) for m in range(months)]


def _stays_dormant(months: int = 18, level: float = 50.0) -> list:
    """Dormant the whole time — quiet baseline, no burst."""
    rng = np.random.default_rng(3)
    return [rng.normal(level, level * 0.2, 21).clip(0) for _ in range(months)]


class TestAssessDormancy:
    def test_dormant_then_surge_is_flagged(self):
        result = assess_dormancy(_dormant_then_active())
        assert result.is_dormancy_break is True
        assert result.dormancy_break >= 0.35
        assert result.dormancy_depth > 0.5
        assert result.activation_strength > 0.5
        assert result.active_volume > result.baseline_volume

    def test_steady_customer_is_not_flagged(self):
        result = assess_dormancy(_steady())
        assert result.is_dormancy_break is False
        assert result.dormancy_break < 0.35

    def test_growth_is_not_mistaken_for_dormancy(self):
        # Ordinary drift (steady growth) must NOT trigger the dormancy flag;
        # that is what the velocity/causal layers are for.
        result = assess_dormancy(_growing())
        assert result.is_dormancy_break is False

    def test_stays_dormant_is_not_flagged(self):
        # Quiet baseline with no burst -> dormant, but not a *break*.
        result = assess_dormancy(_stays_dormant())
        assert result.is_dormancy_break is False
        assert result.activation_strength < 0.2

    def test_insufficient_history_returns_quiet_result(self):
        result = assess_dormancy([np.array([1.0]), np.array([2.0])])
        assert result.is_dormancy_break is False
        assert result.dormancy_break == 0.0

    def test_all_zeros_overall_is_safe(self):
        # >=4 months so we pass the length guard and actually hit the
        # overall < 1e-9 branch — must not divide by zero or flag a break.
        result = assess_dormancy([np.zeros(21) for _ in range(8)])
        assert result.is_dormancy_break is False
        assert result.dormancy_break == 0.0
        assert result.dormancy_depth == 0.0

    def test_custom_thresholds_change_outcome(self):
        # A ~6x jump from a quiet baseline: a high activation_floor makes the
        # burst weaker (or no burst), a low floor makes it stronger.
        series = _dormant_then_active(active_level=300.0)  # ~6x over the 50 baseline
        strict = assess_dormancy(series, activation_floor=20.0)
        lenient = assess_dormancy(series, activation_floor=2.0)
        assert lenient.activation_strength >= strict.activation_strength
        assert lenient.dormancy_break >= strict.dormancy_break

    def test_result_shape(self):
        result = assess_dormancy(_dormant_then_active())
        assert isinstance(result, DormancyResult)
        assert 0.0 <= result.dormancy_break <= 1.0
        assert 0.0 <= result.dormancy_depth <= 1.0
        assert 0.0 <= result.activation_strength <= 1.0

    def test_empty_input_is_safe(self):
        result = assess_dormancy([])
        assert result.is_dormancy_break is False
        assert result.dormancy_break == 0.0


class TestDormancyScenarioEndToEnd:
    """The detector must actually fire on the synthetic book — not only on
    hand-built arrays. Guards against the 'dead branch' regression where the
    scenario existed in code but no customer ever exhibited it."""

    def test_simulator_dormancy_break_customer_is_flagged(self):
        cust = generate_customer(
            drift_id="t-dorm",
            name="Dormant Test AG",
            scenario="dormancy_break",
            drift_start_month=9,
            seed=7,
        )
        result = assess_dormancy(cust.monthly_volume)
        assert result.is_dormancy_break is True
        assert result.active_volume > result.baseline_volume

    def test_inject_default_start_month_still_aligns_and_flags(self):
        # The /drift/inject path calls generate_customer with the DEFAULT
        # drift_start_month (8), which would misalign with the detector's
        # baseline/active split (month 9) if not snapped. generate_customer
        # snaps it, so an injected dormancy break must still fire.
        cust = generate_customer(
            drift_id="t-inject",
            name="Injected Dormant AG",
            scenario="dormancy_break",  # no drift_start_month override
            seed=11,
        )
        assert cust.drift_start_month == 9  # snapped to round(18 * 0.5)
        assert assess_dormancy(cust.monthly_volume).is_dormancy_break is True

    def test_book_contains_a_flagged_dormant_customer(self):
        book = generate_book()
        flagged = [
            c for c in book
            if c.scenario == "dormancy_break"
            and assess_dormancy(c.monthly_volume).is_dormancy_break
        ]
        assert flagged, "expected at least one dormant customer that fires the detector"

    def test_no_non_dormant_scenario_falsely_flags(self):
        # The dormancy layer must stay orthogonal to ordinary drift: NO scenario
        # other than dormancy_break may trip the detector. Each starts from a
        # flat (non-dormant) baseline, so depth -> 0.
        book = generate_book()
        for c in book:
            if c.scenario != "dormancy_break":
                assert assess_dormancy(c.monthly_volume).is_dormancy_break is False, c.scenario
