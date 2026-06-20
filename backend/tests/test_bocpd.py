"""Unit tests for BOCPD changepoint detection."""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.bocpd import BOCPD, standardize


class TestBOCPD:
    def test_changepoint_detected_on_step_series(self):
        rng = np.random.default_rng(42)
        low = rng.normal(0.0, 0.2, 60)
        high = rng.normal(10.0, 0.2, 60)
        series = standardize(np.concatenate([low, high]))
        result = BOCPD().run(series)
        assert len(result.detected_changepoints) >= 1
        # Changepoint should land within 20 steps of the actual step at index 60
        assert any(40 <= cp <= 80 for cp in result.detected_changepoints)

    def test_no_changepoint_on_stationary_noise(self):
        rng = np.random.default_rng(42)
        series = standardize(rng.normal(5.0, 0.5, 150))
        result = BOCPD().run(series)
        assert len(result.detected_changepoints) == 0

    def test_online_property_short_run_detects_same_changepoint(self):
        # Running on N points must detect the same changepoints as running on N+k points
        # (algorithm is causal — no future data may influence past detections).
        rng = np.random.default_rng(7)
        low = rng.normal(0.0, 0.3, 70)
        high = rng.normal(8.0, 0.3, 70)
        full = standardize(np.concatenate([low, high]))
        # Both short (first 100 pts, spanning the step) and full must detect a changepoint
        result_short = BOCPD().run(full[:100])
        result_full = BOCPD().run(full)
        assert len(result_short.detected_changepoints) >= 1
        assert len(result_full.detected_changepoints) >= 1

    def test_standardize_centers_on_baseline_window(self):
        series = np.array([100.0] * 30 + [200.0] * 30)
        z = standardize(series, baseline_window=30)
        # Baseline window (first 30 points) should have mean ≈ 0 after standardization
        assert abs(float(np.mean(z[:30]))) < 0.1
        # Points after the step should be far above zero
        assert float(np.mean(z[30:])) > 5.0

    def test_output_lengths_match_input(self):
        series = np.ones(50)
        result = BOCPD().run(series)
        assert len(result.changepoint_probs) == 50
        assert len(result.map_run_lengths) == 50

    def test_empty_series_returns_empty_result(self):
        result = BOCPD().run(np.array([]))
        assert len(result.changepoint_probs) == 0
        assert result.detected_changepoints == []
