"""Unit tests for cost-aware cascade tier routing."""

from __future__ import annotations

import pytest

from app.drift.cascade import TIER_COST, CascadeReport, CascadeRouter, CustomerSignal, Tier


@pytest.fixture
def router() -> CascadeRouter:
    # Default thresholds: t1=30.0, t2=55.0, t2_value_floor=0.5
    return CascadeRouter()


class TestTierRouting:
    def test_low_drift_stays_at_t0(self, router: CascadeRouter):
        decision = router.route_one(CustomerSignal("c1", drift_score=20.0))
        assert decision.reached_tier == Tier.T0_RULES

    def test_exactly_at_t1_threshold_escalates(self, router: CascadeRouter):
        # score == t1_threshold (30) → escalates to T1
        decision = router.route_one(CustomerSignal("c2", drift_score=30.0))
        assert decision.reached_tier == Tier.T1_ML

    def test_medium_drift_with_low_value_stays_at_t1(self, router: CascadeRouter):
        # score 40 clears T1, but case_value 0.3 < t2_value_floor 0.5 → stays T1
        decision = router.route_one(CustomerSignal("c3", drift_score=40.0, case_value=0.3))
        assert decision.reached_tier == Tier.T1_ML

    def test_high_drift_with_sufficient_value_reaches_t2(self, router: CascadeRouter):
        decision = router.route_one(CustomerSignal("c4", drift_score=60.0, case_value=1.0))
        assert decision.reached_tier == Tier.T2_LLM

    def test_sanctions_hit_with_value_reaches_t2(self, router: CascadeRouter):
        # Deterministic sanctions hit + sufficient case value → T2 regardless of drift score
        decision = router.route_one(
            CustomerSignal("c5", drift_score=5.0, sanctions_hit=True, case_value=1.0)
        )
        assert decision.reached_tier == Tier.T2_LLM

    def test_sanctions_hit_with_low_value_stays_at_t1(self, router: CascadeRouter):
        # Sanctions → T1, but value too low for T2 deep analysis
        decision = router.route_one(
            CustomerSignal("c6", drift_score=5.0, sanctions_hit=True, case_value=0.1)
        )
        assert decision.reached_tier == Tier.T1_ML

    def test_contagion_risk_can_escalate_to_t2(self, router: CascadeRouter):
        # Low drift_score but high propagated_risk → effective_risk pushes to T2
        decision = router.route_one(
            CustomerSignal("c7", drift_score=35.0, propagated_risk=0.60, case_value=1.0)
        )
        # effective_risk = max(35, 0.60 * 100) = 60 >= 55
        assert decision.reached_tier == Tier.T2_LLM

    def test_escalation_reasons_populated_when_escalated(self, router: CascadeRouter):
        decision = router.route_one(CustomerSignal("c8", drift_score=60.0, case_value=1.0))
        assert len(decision.escalation_reasons) > 0

    def test_no_reasons_at_t0(self, router: CascadeRouter):
        decision = router.route_one(CustomerSignal("c9", drift_score=10.0))
        assert decision.escalation_reasons == []


class TestCascadeReport:
    def _make_signals(self) -> list[CustomerSignal]:
        return [
            CustomerSignal("low", drift_score=10.0),                       # T0
            CustomerSignal("mid", drift_score=40.0, case_value=0.3),       # T1
            CustomerSignal("high", drift_score=60.0, case_value=1.0),      # T2
        ]

    def test_total_customers_count(self, router: CascadeRouter):
        report = router.route_book(self._make_signals())
        assert report.total_customers == 3

    def test_cumulative_cost_ordering(self, router: CascadeRouter):
        report = router.route_book(self._make_signals())
        # T2 LLM cost per-customer is highest; T1 ML is next; T0 is free
        assert TIER_COST[Tier.T2_LLM] > TIER_COST[Tier.T1_ML] > TIER_COST[Tier.T0_RULES]
        # In aggregate the T2 bucket should carry more cost than T1
        assert report.tier_costs["T2_LLM"] > report.tier_costs["T1_ML"]

    def test_tier_counts_sum_to_total(self, router: CascadeRouter):
        report = router.route_book(self._make_signals())
        total = sum(report.tier_counts.values())
        assert total == report.total_customers

    def test_summary_line_is_non_empty_string(self, router: CascadeRouter):
        report = router.route_book(self._make_signals())
        line = report.summary_line()
        assert isinstance(line, str)
        assert len(line) > 0

    def test_empty_book_produces_zero_cost(self, router: CascadeRouter):
        report = router.route_book([])
        assert report.total_cost == 0.0
        assert report.total_customers == 0
