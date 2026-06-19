"""Unit tests for suspicious stability (slow-walker) detector."""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.stability import StabilityResult, assess_stability, cohort_volatility


def _flat_monthly(n: int = 24, mean: float = 5000.0, noise_pct: float = 0.02) -> list:
    """Monthly arrays with near-zero month-to-month variance (robotic profile)."""
    rng = np.random.default_rng(0)
    return [rng.normal(mean, mean * noise_pct, 21) for _ in range(n)]


def _volatile_monthly(n: int = 24, base: float = 5000.0) -> list:
    """Monthly arrays with large month-to-month swings (normal business jitter)."""
    rng = np.random.default_rng(1)
    means = rng.uniform(base * 0.5, base * 1.8, n)
    return [rng.normal(m, m * 0.15, 21) for m in means]


def _trending_monthly(n: int = 18, start: float = 0.05, end: float = 0.40) -> list:
    """Monthly arrays whose mean grows from `start` to `end` — simulates risky environment."""
    rng = np.random.default_rng(2)
    means = np.linspace(start, end, n)
    return [rng.normal(m, 0.02, 21) for m in means]


class TestAssessStability:
    def test_flat_customer_in_volatile_cohort_is_suspicious(self):
        flat = _flat_monthly()
        result = assess_stability(
            flat,
            cohort_cv=0.40,
            counterparty_monthly=_trending_monthly(),
            public_risk=0.6,
        )
        assert result.is_suspicious is True
        assert result.suspicion > 0.35

    def test_volatile_customer_matching_cohort_is_not_suspicious(self):
        volatile = _volatile_monthly()
        result = assess_stability(volatile, cohort_cv=0.30)
        assert result.is_suspicious is False

    def test_quiet_environment_does_not_flag_even_flat_customer(self):
        # Product rule: stability_anomaly * env_movement; env=0 → suspicion=0
        flat = _flat_monthly()
        result = assess_stability(flat, cohort_cv=0.40, public_risk=0.0)
        assert result.is_suspicious is False

    def test_suspicion_is_bounded_0_to_1(self):
        flat = _flat_monthly(noise_pct=0.001)
        result = assess_stability(
            flat,
            cohort_cv=0.50,
            counterparty_monthly=_trending_monthly(),
            public_risk=1.0,
        )
        assert 0.0 <= result.suspicion <= 1.0

    def test_stability_anomaly_high_when_customer_much_flatter_than_cohort(self):
        flat = _flat_monthly(noise_pct=0.001)
        result = assess_stability(flat, cohort_cv=0.50)
        assert result.stability_anomaly > 0.5

    def test_own_volatility_lower_than_cohort_for_flat_customer(self):
        flat = _flat_monthly()
        result = assess_stability(flat, cohort_cv=0.40)
        assert result.own_volatility < result.cohort_volatility

    def test_result_fields_match_fixture(self):
        flat = _flat_monthly()
        result = assess_stability(flat, cohort_cv=0.40)
        assert result.cohort_volatility == pytest.approx(0.40)
        assert isinstance(result.detail, str)
        assert len(result.detail) > 0


class TestCohortVolatility:
    def test_returns_positive_for_noisy_book(self):
        book = [_volatile_monthly() for _ in range(8)]
        cv = cohort_volatility(book)
        assert cv > 0.0

    def test_fallback_for_empty_book(self):
        assert cohort_volatility([]) == pytest.approx(0.05)

    def test_flat_book_returns_low_cohort_cv(self):
        # All customers perfectly flat → cohort_cv near zero
        book = [_flat_monthly(noise_pct=0.001) for _ in range(6)]
        cv = cohort_volatility(book)
        assert cv < 0.05

    def test_volatile_book_returns_high_cohort_cv(self):
        book = [_volatile_monthly() for _ in range(6)]
        cv = cohort_volatility(book)
        assert cv > 0.10
