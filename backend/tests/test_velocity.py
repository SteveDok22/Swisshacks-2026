"""Unit tests for drift velocity (KL divergence + velocity band)."""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.velocity import DriftSeries, compute_drift_series, gaussian_kl_bits, velocity_band


class TestGaussianKLBits:
    def test_identical_distributions_are_zero(self):
        assert gaussian_kl_bits(5.0, 2.0, 5.0, 2.0) == pytest.approx(0.0, abs=1e-9)

    def test_zero_mean_shift_is_zero(self):
        assert gaussian_kl_bits(0.0, 1.0, 0.0, 1.0) == pytest.approx(0.0, abs=1e-9)

    def test_positive_for_shifted_mean(self):
        assert gaussian_kl_bits(0.0, 1.0, 5.0, 1.0) > 0.0

    def test_monotonically_increases_with_mean_shift(self):
        kl1 = gaussian_kl_bits(0.0, 1.0, 1.0, 1.0)
        kl2 = gaussian_kl_bits(0.0, 1.0, 3.0, 1.0)
        kl3 = gaussian_kl_bits(0.0, 1.0, 7.0, 1.0)
        assert kl1 < kl2 < kl3

    def test_always_non_negative(self):
        for mu1 in [-10.0, -1.0, 0.0, 1.0, 10.0]:
            assert gaussian_kl_bits(0.0, 1.0, mu1, 1.0) >= 0.0

    def test_symmetric_mean_shifts_give_same_kl(self):
        # KL(N(0,1) || N(d,1)) = KL(N(0,1) || N(-d,1)) since it only depends on (mu0-mu1)^2
        assert gaussian_kl_bits(0.0, 1.0, 3.0, 1.0) == pytest.approx(
            gaussian_kl_bits(0.0, 1.0, -3.0, 1.0), abs=1e-9
        )


class TestVelocityBand:
    def test_natural_band_low_end(self):
        assert velocity_band(0.0) == "natural"

    def test_natural_band_high_end(self):
        assert velocity_band(0.29) == "natural"

    def test_notable_band(self):
        assert velocity_band(0.30) == "notable"
        assert velocity_band(0.79) == "notable"

    def test_structural_band(self):
        assert velocity_band(0.80) == "structural"
        assert velocity_band(2.99) == "structural"

    def test_rapid_band(self):
        assert velocity_band(3.0) == "rapid"
        assert velocity_band(50.0) == "rapid"


class TestComputeDriftSeries:
    def _stable_windows(self, n: int = 12, mean: float = 1000.0) -> dict:
        rng = np.random.default_rng(0)
        return {"monthly_volume": [rng.normal(mean, 50.0, 21) for _ in range(n)]}

    def _step_windows(self, n: int = 14, step_at: int = 6, low: float = 1000.0, high: float = 5000.0) -> dict:
        rng = np.random.default_rng(1)
        windows = []
        for i in range(n):
            mean = high if i >= step_at else low
            windows.append(rng.normal(mean, 50.0, 21))
        return {"monthly_volume": windows}

    def test_returns_empty_when_not_enough_windows(self):
        ds = compute_drift_series(self._stable_windows(n=3), baseline_windows=3)
        assert ds.windows == []
        assert ds.drift_bits == []

    def test_output_lengths_consistent(self):
        ds = compute_drift_series(self._stable_windows(n=12), baseline_windows=3)
        assert len(ds.drift_bits) == len(ds.windows)
        assert len(ds.velocity) == len(ds.windows)
        assert len(ds.acceleration) == len(ds.windows)

    def test_velocity_positive_after_step_change(self):
        ds = compute_drift_series(self._step_windows(), baseline_windows=3)
        # After the step, drift_bits should be large and at least some velocity values positive
        assert any(v > 0 for v in ds.velocity)
        # The max drift_bits after the step should be substantial
        assert max(ds.drift_bits) > 1.0

    def test_stable_data_has_low_drift(self):
        # Stable data should produce near-zero drift bits
        ds = compute_drift_series(self._stable_windows(n=18), baseline_windows=3)
        assert max(ds.drift_bits) < 2.0

    def test_mismatched_metric_lengths_raises(self):
        windows = {
            "monthly_volume": [np.ones(21)] * 10,
            "counterparty_risk": [np.ones(21)] * 8,  # different length
        }
        with pytest.raises(ValueError):
            compute_drift_series(windows)
