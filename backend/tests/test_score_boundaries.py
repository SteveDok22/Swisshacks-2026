"""
Unit tests for pure scoring functions — no I/O, no app startup.

These cover the mathematical boundaries of the drift engine's building blocks:
- velocity_band() interpretation thresholds
- gaussian_kl_bits() divergence properties
- standardize() z-scoring
- BOCPD changepoint behaviour on clean signals

Run: pytest tests/test_score_boundaries.py -v
"""

import numpy as np
import pytest

from app.drift.velocity import velocity_band, gaussian_kl_bits
from app.drift.bocpd import standardize, BOCPD


class TestVelocityBand:
    def test_zero_is_natural(self):
        assert velocity_band(0.0) == "natural"

    def test_just_below_natural_boundary(self):
        assert velocity_band(0.29) == "natural"

    def test_natural_boundary_is_notable(self):
        assert velocity_band(0.30) == "notable"

    def test_mid_notable(self):
        assert velocity_band(0.5) == "notable"

    def test_just_below_structural(self):
        assert velocity_band(0.79) == "notable"

    def test_notable_boundary_is_structural(self):
        assert velocity_band(0.80) == "structural"

    def test_mid_structural(self):
        assert velocity_band(1.5) == "structural"

    def test_just_below_rapid(self):
        assert velocity_band(2.99) == "structural"

    def test_structural_boundary_is_rapid(self):
        assert velocity_band(3.00) == "rapid"

    def test_high_velocity_is_rapid(self):
        assert velocity_band(12.0) == "rapid"

    def test_band_is_one_of_four(self):
        for dv in [0.0, 0.4, 1.0, 5.0, 100.0]:
            assert velocity_band(dv) in {"natural", "notable", "structural", "rapid"}


class TestGaussianKL:
    def test_identical_distributions_zero(self):
        assert gaussian_kl_bits(0.0, 1.0, 0.0, 1.0) == pytest.approx(0.0, abs=1e-9)

    def test_mean_shift_is_positive(self):
        assert gaussian_kl_bits(0.0, 1.0, 2.0, 1.0) > 0.0

    def test_larger_mean_shift_larger_kl(self):
        small = gaussian_kl_bits(0.0, 1.0, 1.0, 1.0)
        large = gaussian_kl_bits(0.0, 1.0, 3.0, 1.0)
        assert large > small

    def test_variance_change_is_positive(self):
        assert gaussian_kl_bits(0.0, 1.0, 0.0, 4.0) > 0.0

    def test_kl_never_negative(self):
        for mu1 in [-3.0, 0.0, 2.5]:
            for var1 in [0.5, 1.0, 5.0]:
                assert gaussian_kl_bits(0.0, 1.0, mu1, var1) >= -1e-9


class TestStandardize:
    def test_output_same_length(self):
        s = np.arange(50, dtype=float)
        out = standardize(s, baseline_window=30)
        assert len(out) == len(s)

    def test_constant_series_no_nan(self):
        s = np.ones(40)
        out = standardize(s, baseline_window=30)
        assert not np.any(np.isnan(out))

    def test_returns_numpy_array(self):
        out = standardize(np.arange(40, dtype=float), baseline_window=30)
        assert isinstance(out, np.ndarray)


class TestBOCPD:
    def test_no_changepoint_on_stationary(self):
        rng = np.random.default_rng(0)
        series = standardize(rng.normal(0.0, 1.0, 120), baseline_window=30)
        result = BOCPD().run(series)
        assert all(cp > 30 for cp in result.detected_changepoints)

    def test_detects_step_change(self):
        rng = np.random.default_rng(1)
        first = rng.normal(0.0, 0.5, 60)
        second = rng.normal(6.0, 0.5, 60)
        series = standardize(np.concatenate([first, second]), baseline_window=30)
        result = BOCPD().run(series)
        assert len(result.detected_changepoints) > 0
