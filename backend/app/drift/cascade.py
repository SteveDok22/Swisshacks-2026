"""
Cost-aware cascade router (BR7).

AMINA's explicit criterion: "cheap models filter first and heavy reasoning
only kicks in for high risk cases."

We formalize escalation as an information-economics rule:

    escalate case c from tier k to k+1
        iff  E[information gain] * value(c) > cost(k+1)

Three tiers:
    T0 — deterministic rules + BOCPD + consistency  (~$0,    100% of book)
    T1 — embeddings + ownership graph PageRank       (~$0.0002, anomalous only)
    T2 — Claude deep reasoning + RFI generation      (~$0.03-0.10, uncertain band)

The router runs T0 on everyone, escalates only flagged customers to T1, and
only the still-uncertain to T2 — producing a live cost report the dashboard
renders ("1,000 screened: $0.18; 12 deep-analyzed: $0.43").

No external dependencies — pure orchestration logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Tier(IntEnum):
    T0_RULES = 0
    T1_ML = 1
    T2_LLM = 2


# Per-customer cost in USD by tier (illustrative, defensible orders of magnitude)
TIER_COST = {
    Tier.T0_RULES: 0.0,
    Tier.T1_ML: 0.0002,
    Tier.T2_LLM: 0.05,
}


@dataclass
class TierDecision:
    """Why a customer was (or wasn't) escalated."""

    drift_id: str
    reached_tier: Tier
    drift_score: float
    escalation_reasons: list[str] = field(default_factory=list)


@dataclass
class CascadeReport:
    """Aggregate cost + flow report for one scan pass."""

    total_customers: int
    tier_counts: dict[str, int]
    tier_costs: dict[str, float]
    total_cost: float
    decisions: list[TierDecision]

    def summary_line(self) -> str:
        t1 = self.tier_counts.get("T1_ML", 0)
        t2 = self.tier_counts.get("T2_LLM", 0)
        return (
            f"{self.total_customers} screened: ${self.tier_costs.get('T0_RULES', 0):.2f}; "
            f"{t1} to ML: ${self.tier_costs.get('T1_ML', 0):.4f}; "
            f"{t2} to deep analysis: ${self.tier_costs.get('T2_LLM', 0):.2f}; "
            f"total ${self.total_cost:.2f}"
        )


@dataclass
class CustomerSignal:
    """Inputs the cascade router decides on (produced by the passive layers)."""

    drift_id: str
    drift_score: float            # 0..100, from velocity + BOCPD fusion (T0)
    sanctions_hit: bool = False   # Layer 1 deterministic (T0)
    propagated_risk: float = 0.0  # Layer 3 contagion (computed in T1)
    case_value: float = 1.0       # relative importance (e.g. AUM-weighted)


class CascadeRouter:
    """
    Routes customers through escalating analysis tiers based on signal
    strength and information-economics.
    """

    def __init__(
        self,
        t1_drift_threshold: float = 30.0,
        t2_drift_threshold: float = 55.0,
        t2_value_floor: float = 0.5,
    ) -> None:
        # T0 -> T1: any non-trivial drift OR a deterministic hit
        self.t1_drift_threshold = t1_drift_threshold
        # T1 -> T2: high drift / contagion, gated by case value
        self.t2_drift_threshold = t2_drift_threshold
        self.t2_value_floor = t2_value_floor

    def route_one(self, signal: CustomerSignal) -> TierDecision:
        reasons: list[str] = []
        tier = Tier.T0_RULES

        # T0 -> T1 escalation
        if signal.sanctions_hit:
            tier = Tier.T1_ML
            reasons.append("deterministic sanctions/PEP hit")
        elif signal.drift_score >= self.t1_drift_threshold:
            tier = Tier.T1_ML
            reasons.append(
                f"drift score {signal.drift_score:.0f} >= {self.t1_drift_threshold:.0f}"
            )

        # T1 -> T2 escalation (only if already at T1)
        if tier >= Tier.T1_ML:
            effective_risk = max(signal.drift_score, signal.propagated_risk * 100.0)
            value_ok = signal.case_value >= self.t2_value_floor
            if signal.sanctions_hit and value_ok:
                tier = Tier.T2_LLM
                reasons.append("sanctions hit warrants deep reasoning")
            elif effective_risk >= self.t2_drift_threshold and value_ok:
                tier = Tier.T2_LLM
                reasons.append(
                    f"effective risk {effective_risk:.0f} >= {self.t2_drift_threshold:.0f}, "
                    f"case value {signal.case_value:.2f} clears floor"
                )
            elif effective_risk >= self.t2_drift_threshold and not value_ok:
                reasons.append(
                    f"risk high but case value {signal.case_value:.2f} below floor "
                    f"{self.t2_value_floor:.2f} — deep analysis not cost-justified"
                )

        return TierDecision(
            drift_id=signal.drift_id,
            reached_tier=tier,
            drift_score=signal.drift_score,
            escalation_reasons=reasons,
        )

    def route_book(self, signals: list[CustomerSignal]) -> CascadeReport:
        """Run the full cascade over a book and produce a cost report."""
        decisions = [self.route_one(s) for s in signals]

        # Cost accounting: a customer reaching tier k incurs the cost of
        # EVERY tier up to and including k (the work was actually done).
        tier_counts = {t.name: 0 for t in Tier}
        tier_costs = {t.name: 0.0 for t in Tier}

        for d in decisions:
            for t in Tier:
                if t <= d.reached_tier:
                    tier_costs[t.name] += TIER_COST[t]
            tier_counts[d.reached_tier.name] += 1

        total_cost = sum(tier_costs.values())

        return CascadeReport(
            total_customers=len(signals),
            tier_counts=tier_counts,
            tier_costs=tier_costs,
            total_cost=total_cost,
            decisions=decisions,
        )
