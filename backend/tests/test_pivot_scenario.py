"""
Tests for the `pivot` synthetic scenario (UC 10, Centra Tech pattern).

The transaction-level half lives in ``drift/simulator.py``: a public
business-model pivot is risk-shaped — volume climbs while margin collapses as the
raised capital flows straight through. The public-signal half (news pivot cluster
+ website cosine shift + funding co-occurrence) is covered in
``test_public_intel_aggregator.py``.
"""

from __future__ import annotations

import numpy as np

from app.drift.simulator import SCENARIOS, generate_customer


class TestPivotScenario:
    def test_pivot_is_a_registered_scenario(self):
        assert "pivot" in SCENARIOS

    def test_pivot_causal_truth_is_risk(self):
        cust = generate_customer("p1", "Centra Holdings AG", "pivot", seed=7)
        assert cust.causal_truth == "risk"

    def test_pivot_has_drift_onset_and_terminal_listing(self):
        cust = generate_customer("p1", "Centra Holdings AG", "pivot", months=18, seed=7)
        # Non-stable scenario: drift onset is set and a terminal listing lands last.
        assert cust.drift_start_month is not None
        assert cust.sanctions_month == cust.months - 1

    def test_pivot_volume_rises_and_margin_collapses(self):
        # The risk signature: volume up, retention down. Compare the pre-onset
        # baseline month against the final (fully-drifted) month.
        cust = generate_customer(
            "p1", "Centra Holdings AG", "pivot",
            months=18, drift_start_month=8, seed=7,
        )
        baseline_vol = float(np.mean(cust.monthly_volume[0]))
        final_vol = float(np.mean(cust.monthly_volume[-1]))
        baseline_margin = float(np.mean(cust.margin_ratio[0]))
        final_margin = float(np.mean(cust.margin_ratio[-1]))

        assert final_vol > baseline_vol * 1.5, "volume should climb materially"
        assert final_margin < baseline_margin * 0.5, "margin should collapse toward transit"

    def test_pivot_is_deterministic_under_seed(self):
        a = generate_customer("p1", "Centra Holdings AG", "pivot", seed=7)
        b = generate_customer("p1", "Centra Holdings AG", "pivot", seed=7)
        assert np.allclose(a.daily_volume_series(), b.daily_volume_series())
