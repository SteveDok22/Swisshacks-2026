"""Hypothesis H3 — Risk propagates through ownership topology.

    "Risk propagates through ownership topology ahead of public disclosure."
     (README, Hypotheses and Validation — validated via personalized PageRank
      from a sanctioned seed.)

When an entity is sanctioned, customers a couple of ownership hops away light
up via propagation even though they are themselves on no list — while customers
far from the seed, or unconnected to it, stay quiet. We test the topology decay
directly: 2-hop customers are elevated above an alert threshold; 3-or-more-hop
customers are not; unconnected customers receive negligible propagated risk.
"""

from __future__ import annotations

import pytest

from app.drift.contagion import OwnershipGraph, build_demo_graph

# Above this propagated-risk value a customer is "elevated" for review. Matches
# the 0.1 alert level asserted in tests/features/contagion.feature
# ("... has propagated_risk above 0.1").
ELEVATED_THRESHOLD = 0.1
# Personalized PageRank leaves a tiny numerical residual on nodes in a separate
# component (power iteration stops at a finite tolerance); anything below this
# is effectively zero propagated risk.
NEGLIGIBLE_RISK = 1e-3


def _branching_shell_graph() -> OwnershipGraph:
    """A realistic shell structure. The seed owns two shells; risk dilutes as it
    branches and descends, so 2-hop customers stay elevated while deeper ones
    fall below the alert threshold.

        SEED
         ├─ ShellA ─ c2a (2 hops)
         │        └─ SubShell ─ c3a (3 hops)
         │                    └─ SubShell2 ─ c4a (4 hops)
         └─ ShellB ─ c2b (2 hops)

        CleanHolding ─ cX   (unconnected to the seed)
    """
    g = OwnershipGraph()
    g.add_entity("SEED", name="Sanctioned Entity")

    g.add_entity("ShellA", entity_type="shell")
    g.add_entity("ShellB", entity_type="shell")
    g.add_ownership("SEED", "ShellA", 0.5)
    g.add_ownership("SEED", "ShellB", 0.5)

    g.add_entity("c2a", is_customer=True)
    g.add_entity("c2b", is_customer=True)
    g.add_ownership("ShellA", "c2a", 0.4)
    g.add_ownership("ShellB", "c2b", 0.4)

    g.add_entity("SubShell", entity_type="shell")
    g.add_entity("c3a", is_customer=True)
    g.add_ownership("ShellA", "SubShell", 0.4)
    g.add_ownership("SubShell", "c3a", 0.4)

    g.add_entity("SubShell2", entity_type="shell")
    g.add_entity("c4a", is_customer=True)
    g.add_ownership("SubShell", "SubShell2", 0.4)
    g.add_ownership("SubShell2", "c4a", 0.4)

    g.add_entity("CleanHolding", entity_type="company")
    g.add_entity("cX", is_customer=True)
    g.add_ownership("CleanHolding", "cX", 0.5)
    return g


@pytest.fixture(scope="module")
def branching_result():
    return _branching_shell_graph().propagate(["SEED"])


@pytest.fixture(scope="module")
def demo_result():
    drift_ids = [f"drift-{i:03d}" for i in range(1, 16)]
    return build_demo_graph(drift_ids).propagate(["SANCTIONED_ENTITY"])


class TestH3TopologyDecay:
    def test_two_hop_customers_are_elevated(self, branching_result):
        for cid in ("c2a", "c2b"):
            assert branching_result.hops_from_seed[cid] == 2
            assert branching_result.propagated_risk[cid] > ELEVATED_THRESHOLD, (
                f"2-hop customer {cid} not elevated: {branching_result.propagated_risk[cid]:.4f}"
            )

    def test_three_or_more_hop_customers_are_not_elevated(self, branching_result):
        for cid in ("c3a", "c4a"):
            assert branching_result.hops_from_seed[cid] >= 3
            assert branching_result.propagated_risk[cid] <= ELEVATED_THRESHOLD, (
                f"{branching_result.hops_from_seed[cid]}-hop customer {cid} "
                f"unexpectedly elevated: {branching_result.propagated_risk[cid]:.4f}"
            )

    def test_unconnected_customer_receives_negligible_risk(self, branching_result):
        assert branching_result.hops_from_seed.get("cX") is None
        assert branching_result.propagated_risk["cX"] < NEGLIGIBLE_RISK

    def test_risk_decays_monotonically_with_hop_distance(self, branching_result):
        risks = [branching_result.propagated_risk[c] for c in ("c2a", "c3a", "c4a")]
        assert risks[0] > risks[1] > risks[2], (
            f"propagated risk did not decay monotonically with hops: {risks}"
        )


class TestH3DemoGraph:
    """The shipped demo graph must exhibit the same property: the two wired
    customers (2 hops via shells) are elevated; the rest are untouched.

    "drift-003" (Alpine Logistics) and "drift-008" (Bernina Wealth) are the
    customers wired 2 hops from SANCTIONED_ENTITY in build_demo_graph
    (app/drift/contagion.py). If the demo graph topology changes, update these
    IDs to match.
    """

    def test_wired_two_hop_customers_are_elevated(self, demo_result):
        for cid in ("drift-003", "drift-008"):
            assert demo_result.hops_from_seed[cid] == 2
            assert demo_result.propagated_risk[cid] > ELEVATED_THRESHOLD

    def test_distant_customers_are_not_elevated(self, demo_result):
        for cid in ("drift-001", "drift-002", "drift-005"):
            assert demo_result.propagated_risk[cid] <= ELEVATED_THRESHOLD

    def test_ranking_puts_wired_customers_on_top(self, demo_result):
        top_two = {cid for cid, _ in demo_result.ranked_customers[:2]}
        assert top_two == {"drift-003", "drift-008"}
