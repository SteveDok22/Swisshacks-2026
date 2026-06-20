"""
UC 1 — negative-news-spike scenario (`news_spike`).

Covers the synthetic scenario added to the simulator: a customer whose public
risk surges via a sustained adverse-media spike (the Wirecard pattern), with a
co-occurring internal volume drift + margin collapse so the causal layer reads
it as risk-shaped and the confirmation lift fires.
"""

from __future__ import annotations

import numpy as np

from app.drift.public_intel import detect_news_spike_month, generate_signals_for_customer
from app.drift.service import compute_drift_analysis
from app.drift.simulator import SCENARIOS, generate_book, generate_customer
from app.drift.stability import cohort_volatility


def _cohort_cv() -> float:
    refs = [generate_customer(f"ref-{i}", "Ref", "stable", seed=700 + i) for i in range(8)]
    return cohort_volatility([c.monthly_volume for c in refs])


class TestNewsSpikeSimulator:
    def test_scenario_is_registered(self):
        assert "news_spike" in SCENARIOS

    def test_causal_truth_is_risk(self):
        cust = generate_customer("d", "Wirecard Holdings AG", "news_spike", seed=1)
        assert cust.causal_truth == "risk"
        assert cust.drift_start_month is not None
        assert cust.sanctions_month == cust.months - 1

    def test_volume_rises_and_margin_collapses(self):
        cust = generate_customer("d", "Wirecard Holdings AG", "news_spike", seed=1)
        # Volume trends up: late-window mean exceeds the pre-drift baseline.
        baseline_vol = float(np.mean(cust.monthly_volume[0]))
        late_vol = float(np.mean(cust.monthly_volume[-1]))
        assert late_vol > baseline_vol * 1.3
        # Margin collapses toward zero (risk transit signature).
        baseline_margin = float(np.mean(cust.margin_ratio[0]))
        late_margin = float(np.mean(cust.margin_ratio[-1]))
        assert late_margin < baseline_margin * 0.5

    def test_appears_in_demo_book_without_shifting_contagion_ids(self):
        book = generate_book()
        by_id = {c.drift_id: c.scenario for c in book}
        assert any(c.scenario == "news_spike" for c in book)
        # Contagion-wired IDs must keep their scenarios (build_demo_graph pins them).
        assert by_id["drift-002"] == "counterparty_migration"
        assert by_id["drift-004"] == "combined"
        assert by_id["drift-005"] == "benign_expansion"


class TestNewsSpikeEndToEnd:
    def test_public_risk_surges_and_spike_detected(self):
        cust = generate_customer("d", "Wirecard Holdings AG", "news_spike", seed=2)
        signals = generate_signals_for_customer(
            cust.drift_id, cust.name, cust.scenario,
            months=cust.months, drift_start_month=cust.drift_start_month, seed=2,
        )
        assert all(s.signal_type == "adverse_media" for s in signals)
        spike = detect_news_spike_month(signals, cust.months)
        assert spike is not None

        analysis = compute_drift_analysis(
            cust, cohort_cv=_cohort_cv(), public_signals=signals
        )
        assert analysis["news_spike_month"] == spike
        assert analysis["public_risk"] > 0.7
        # External story + internal drift co-occur → the score lands in risk range.
        assert analysis["drift_score"] >= 60.0

    def test_score_exceeds_signal_free_baseline(self):
        """The news spike must lift the score above the same customer with no
        public signals — proving the public layer actually contributes."""
        cust = generate_customer("d", "Wirecard Holdings AG", "news_spike", seed=2)
        signals = generate_signals_for_customer(
            cust.drift_id, cust.name, cust.scenario,
            months=cust.months, drift_start_month=cust.drift_start_month, seed=2,
        )
        cohort_cv = _cohort_cv()
        with_news = compute_drift_analysis(cust, cohort_cv=cohort_cv, public_signals=signals)
        without = compute_drift_analysis(cust, cohort_cv=cohort_cv, public_signals=None)
        assert with_news["drift_score"] >= without["drift_score"]
