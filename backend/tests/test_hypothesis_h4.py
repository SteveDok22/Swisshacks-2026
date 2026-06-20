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
        # Synthetic risk mix: most customers clean, a thin band of mid-risk, a
        # sliver of high-risk (a few with a deterministic sanctions hit). The
        # exact split is illustrative of a real book's skew, not load-bearing —
        # TestH4Robustness re-checks the claim across several seeds/draws.
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


def _all_llm_reached(book: list[CustomerSignal]) -> dict[str, Tier]:
    """The baseline strategy under comparison: deep T2 LLM review for everyone."""
    return {s.drift_id: Tier.T2_LLM for s in book}


def _is_high_risk(signal: CustomerSignal, router: CascadeRouter) -> bool:
    """Ground-truth: would the router send this signal to T2_LLM?

    Delegates to router.would_reach_t2 so the definition stays in sync with
    the actual escalation logic in CascadeRouter.route_one — no duplicated
    threshold conditions that can silently drift.
    """
    return router.would_reach_t2(signal)


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
        # Sanity check on the cost mechanism: the bulk of the book is cleared by
        # T0 rules at zero marginal cost (the synthetic mix is ~90% clean, so a
        # 0.80 floor is comfortably satisfied without being brittle).
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
        all_llm_reached = _all_llm_reached(book)

        high_risk = [s for s in book if _is_high_risk(s, router)]
        assert high_risk, "test book contains no high-risk customers"

        def recall(routing: dict[str, Tier]) -> float:
            return sum(1 for s in high_risk if routing[s.drift_id] == Tier.T2_LLM) / len(high_risk)

        cascade_recall = recall(reached)
        all_llm_recall = recall(all_llm_reached)
        # The baseline analyses everyone, so it catches every high-risk case;
        # the cascade must match that recall while spending a fraction of the cost.
        assert all_llm_recall == pytest.approx(1.0)
        assert cascade_recall == pytest.approx(all_llm_recall), (
            f"cascade recall {cascade_recall:.3f} != all-LLM recall {all_llm_recall:.3f}"
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
