"""Unit tests for ownership contagion (personalized PageRank)."""

from __future__ import annotations

import pytest

from app.drift.contagion import ContagionResult, OwnershipGraph, OwnershipEdge


def _simple_graph() -> tuple[OwnershipGraph, str, str]:
    """
    seed → cust_direct (1 hop)
    seed → middle → cust_far (2 hops)
    Returns (graph, direct_id, far_id).
    """
    g = OwnershipGraph()
    g.add_entity("seed", name="Sanctioned Entity")
    g.add_entity("middle", name="Shell Co")
    g.add_entity("cust_direct", name="Direct Customer", is_customer=True)
    g.add_entity("cust_far", name="Far Customer", is_customer=True)
    g.add_ownership("seed", "cust_direct", 0.9)
    g.add_ownership("seed", "middle", 0.7)
    g.add_ownership("middle", "cust_far", 0.5)
    return g, "cust_direct", "cust_far"


class TestOwnershipGraphPropagation:
    def test_direct_neighbor_receives_elevated_risk(self):
        g, cust_direct, _ = _simple_graph()
        result = g.propagate(["seed"])
        assert result.propagated_risk[cust_direct] > 0.1

    def test_direct_neighbor_higher_risk_than_far_customer(self):
        g, cust_direct, cust_far = _simple_graph()
        result = g.propagate(["seed"])
        assert result.propagated_risk[cust_direct] > result.propagated_risk[cust_far]

    def test_hops_from_seed_are_counted_correctly(self):
        g, cust_direct, cust_far = _simple_graph()
        result = g.propagate(["seed"])
        assert result.hops_from_seed[cust_direct] == 1
        assert result.hops_from_seed[cust_far] == 2

    def test_seed_itself_has_max_normalized_risk(self):
        g, _, _ = _simple_graph()
        result = g.propagate(["seed"])
        assert result.propagated_risk["seed"] == pytest.approx(1.0)

    def test_ranked_customers_excludes_seeds(self):
        g, _, _ = _simple_graph()
        result = g.propagate(["seed"])
        customer_ids = [cid for cid, _ in result.ranked_customers]
        assert "seed" not in customer_ids

    def test_ranked_customers_sorted_descending(self):
        g, _, _ = _simple_graph()
        result = g.propagate(["seed"])
        scores = [score for _, score in result.ranked_customers]
        assert scores == sorted(scores, reverse=True)

    def test_empty_seeds_returns_empty_result(self):
        g, _, _ = _simple_graph()
        result = g.propagate([])
        assert result.propagated_risk == {}
        assert result.ranked_customers == []

    def test_unknown_seed_is_ignored(self):
        g, _, _ = _simple_graph()
        result = g.propagate(["nonexistent-seed"])
        assert result.propagated_risk == {}


class TestOwnershipGraphBuilding:
    def test_customers_returns_only_customer_nodes(self):
        g = OwnershipGraph()
        g.add_entity("company", name="Shell", is_customer=False)
        g.add_entity("customer", name="Bank Customer", is_customer=True)
        assert g.customers() == ["customer"]

    def test_add_edges_bulk(self):
        g = OwnershipGraph()
        g.add_entity("a")
        g.add_entity("b")
        g.add_entity("c")
        g.add_edges([OwnershipEdge("a", "b", 0.5), OwnershipEdge("b", "c", 0.3)])
        result = g.propagate(["a"])
        assert "b" in result.propagated_risk
        assert "c" in result.propagated_risk


class TestToCytoscape:
    def test_returns_nodes_and_edges_keys(self):
        g, _, _ = _simple_graph()
        result = g.propagate(["seed"])
        cyto = g.to_cytoscape(result)
        assert "nodes" in cyto
        assert "edges" in cyto

    def test_node_count_matches_entity_count(self):
        g, _, _ = _simple_graph()
        cyto = g.to_cytoscape()
        assert len(cyto["nodes"]) == 4  # seed, middle, cust_direct, cust_far

    def test_risk_attached_when_contagion_provided(self):
        g, cust_direct, _ = _simple_graph()
        result = g.propagate(["seed"])
        cyto = g.to_cytoscape(result)
        direct_node = next(n for n in cyto["nodes"] if n["id"] == cust_direct)
        assert direct_node["risk"] > 0.1
