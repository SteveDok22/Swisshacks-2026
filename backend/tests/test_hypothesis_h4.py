"""Hypothesis H4 — A cost-aware cascade preserves recall at a fraction of cost.

    "A cost-aware cascade preserves recall at a fraction of the cost."
     (README, Hypotheses and Validation — validated via cascade vs
      LLM-on-everything on 1,000 customers.)

The baseline strategy runs the expensive T2 LLM on every customer. The cascade
runs cheap deterministic rules on everyone (T0), escalates only the anomalous
to T1 ML, and only the genuinely high-risk / high-value to the T2 LLM. The
claim has two halves:

  1. Cost: the cascade spends well under 10% of the LLM-on-everything bill.
  2. Recall (unchanged): every customer the all-LLM strategy would treat as
     high-risk is still escalated to the T2 LLM by the cascade — no high-risk
     case is dropped to save money.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.cascade import (
    TIER_COST,
    CascadeRouter,
    CustomerSignal,
    Tier,
)

N_CUSTOMERS = 1_000
COST_BUDGET_FRACTION = 0.10  # cascade must cost < 10% of LLM-on-everything


def _synthetic_book(seed: int = 0) -> list[CustomerSignal]:
    """A realistic book: ~90% clean, ~7% mid-risk, ~3% high-risk (some with a
    deterministic sanctions hit). Deterministic via seed."""
    rng = np.random.default_rng(seed)
    signals: list[CustomerSignal] = []
    for i in range(N_CUSTOMERS):
        r = rng.random()
        if r < 0.90:
            score = rng.uniform(0, 25)
            sanctions = False
            value = rng.uniform(0.3, 1.0)
        elif r < 0.97:
            score = rng.uniform(30, 54)
            sanctions = False
            value = rng.uniform(0.5, 1.0)
        else:
            score = rng.uniform(55, 100)
            sanctions = rng.random() < 0.3
            value = rng.uniform(0.6, 1.0)
        signals.append(
            CustomerSignal(f"c{i}", drift_score=score, sanctions_hit=sanctions, case_value=value)
        )
    return signals


def _llm_on_everything_cost(n: int) -> float:
    """Cost of running the T2 LLM on every customer (cumulative through tiers)."""
    return n * sum(TIER_COST[t] for t in Tier)


def _is_high_risk(signal: CustomerSignal, router: CascadeRouter) -> bool:
    """Ground-truth high-risk = a case the deep T2 LLM review is warranted for:
    high effective risk clearing the value floor, or a sanctions hit with value.
    This is exactly the population the all-LLM strategy 'catches'."""
    effective_risk = max(signal.drift_score, signal.propagated_risk * 100.0)
    value_ok = signal.case_value >= router.t2_value_floor
    return value_ok and (signal.sanctions_hit or effective_risk >= router.t2_drift_threshold)


@pytest.fixture(scope="module")
def router() -> CascadeRouter:
    return CascadeRouter()


@pytest.fixture(scope="module")
def book() -> list[CustomerSignal]:
    return _synthetic_book()


class TestH4Cost:
    def test_cascade_costs_under_ten_percent_of_llm_on_everything(self, router, book):
        report = router.route_book(book)
        llm_all = _llm_on_everything_cost(len(book))
        assert report.total_cost < COST_BUDGET_FRACTION * llm_all, (
            f"cascade ${report.total_cost:.2f} is not below 10% of "
            f"LLM-on-everything ${llm_all:.2f} "
            f"({report.total_cost / llm_all:.1%})"
        )

    def test_most_customers_never_leave_the_free_tier(self, router, book):
        report = router.route_book(book)
        # The bulk of the book should be cleared by T0 rules at zero marginal cost.
        assert report.tier_counts["T0_RULES"] > 0.80 * len(book)


class TestH4RecallUnchanged:
    def test_every_high_risk_customer_still_reaches_the_llm(self, router, book):
        report = router.route_book(book)
        reached = {d.drift_id: d.reached_tier for d in report.decisions}

        high_risk = [s for s in book if _is_high_risk(s, router)]
        assert high_risk, "test book contains no high-risk customers"

        missed = [s.drift_id for s in high_risk if reached[s.drift_id] != Tier.T2_LLM]
        assert not missed, (
            f"cascade dropped {len(missed)} high-risk customers that "
            f"LLM-on-everything would have analyzed: {missed[:5]}"
        )

    def test_cascade_recall_equals_all_llm_recall(self, router, book):
        report = router.route_book(book)
        reached = {d.drift_id: d.reached_tier for d in report.decisions}

        high_risk = [s for s in book if _is_high_risk(s, router)]
        # All-LLM analyses everyone, so its recall over the high-risk set is 1.0.
        all_llm_recall = 1.0
        cascade_recall = sum(1 for s in high_risk if reached[s.drift_id] == Tier.T2_LLM) / len(
            high_risk
        )
        assert cascade_recall == pytest.approx(all_llm_recall), (
            f"cascade recall {cascade_recall:.3f} != all-LLM recall {all_llm_recall}"
        )


class TestH4Robustness:
    @pytest.mark.parametrize("seed", [1, 2, 3, 7, 11])
    def test_cost_and_recall_hold_across_seeds(self, router, seed):
        book = _synthetic_book(seed=seed)
        report = router.route_book(book)
        reached = {d.drift_id: d.reached_tier for d in report.decisions}

        llm_all = _llm_on_everything_cost(len(book))
        assert report.total_cost < COST_BUDGET_FRACTION * llm_all

        high_risk = [s for s in book if _is_high_risk(s, router)]
        assert all(reached[s.drift_id] == Tier.T2_LLM for s in high_risk)
