"""Unit tests for the dormancy-break (suspicious activation) detector."""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.dormancy import DormancyResult, assess_dormancy


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
