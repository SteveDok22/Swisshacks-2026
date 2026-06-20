"""Unit tests for ownership contagion (personalized PageRank)."""

from __future__ import annotations

import pytest

from app.drift.contagion import (
    OwnershipEdge,
    OwnershipGraph,
    build_graph_from_snapshots,
)
from app.sources.base import EntitySnapshot


def _snap(
    drift_id: str,
    *,
    lei: str | None = None,
    parents: list[str] | None = None,
    children: list[str] | None = None,
    name: str | None = None,
) -> EntitySnapshot:
    """Build a GLEIF-shaped EntitySnapshot (parent LEI in beneficial_owners,
    child LEIs in officers, own LEI in raw_data)."""
    return EntitySnapshot(
        drift_id=drift_id,
        name=name or drift_id,
        source="gleif",
        beneficial_owners=list(parents or []),
        officers=list(children or []),
        raw_data={"lei": lei} if lei else {},
    )


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
        drift_ids = [cid for cid, _ in result.ranked_customers]
        assert "seed" not in drift_ids

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


class TestBuildGraphFromSnapshots:
    """Build a real ownership graph from GLEIF EntitySnapshots (use case 3)."""

    def test_empty_snapshots_returns_none(self):
        assert build_graph_from_snapshots({}) is None

    def test_no_ownership_links_returns_none(self):
        # Customers with neither parent nor child LEIs carry no edges.
        snaps = {"drift-001": _snap("drift-001", lei="LEI001")}
        assert build_graph_from_snapshots(snaps) is None

    def test_parent_link_creates_owner_to_customer_edge(self):
        snaps = {"drift-001": _snap("drift-001", lei="LEI001", parents=["PARENTLEI"])}
        g = build_graph_from_snapshots(snaps)
        assert g is not None
        # Parent owns the customer → contagion from the parent reaches it.
        result = g.propagate(["PARENTLEI"])
        assert result.propagated_risk["drift-001"] > 0.1
        assert result.hops_from_seed["drift-001"] == 1

    def test_customer_node_is_flagged_as_customer(self):
        snaps = {"drift-001": _snap("drift-001", lei="LEI001", parents=["PARENTLEI"])}
        g = build_graph_from_snapshots(snaps)
        assert g is not None
        assert g.customers() == ["drift-001"]

    def test_external_parent_is_not_a_customer(self):
        snaps = {"drift-001": _snap("drift-001", lei="LEI001", parents=["PARENTLEI"])}
        g = build_graph_from_snapshots(snaps)
        assert g is not None
        assert g.g.nodes["PARENTLEI"]["is_customer"] is False

    def test_child_link_creates_customer_to_child_edge(self):
        snaps = {"drift-001": _snap("drift-001", lei="LEI001", children=["CHILDLEI"])}
        g = build_graph_from_snapshots(snaps)
        assert g is not None
        assert g.g.has_edge("drift-001", "CHILDLEI")

    def test_cross_customer_link_via_shared_lei(self):
        # drift-001's child LEI is drift-002's own LEI → they share one node and
        # contagion can flow from one customer to the other.
        snaps = {
            "drift-001": _snap("drift-001", lei="LEI001", children=["LEI002"]),
            "drift-002": _snap("drift-002", lei="LEI002"),
        }
        g = build_graph_from_snapshots(snaps)
        assert g is not None
        assert g.g.has_edge("drift-001", "drift-002")
        assert "LEI002" not in g.g  # resolved to the customer node, not duplicated

    def test_self_parent_link_is_ignored(self):
        # A snapshot that lists its own LEI as parent must not create a self-loop.
        snaps = {"drift-001": _snap("drift-001", lei="LEI001", parents=["LEI001"])}
        assert build_graph_from_snapshots(snaps) is None


class TestBuildGraphFromSnapshotsSeeded:
    """Inject a flagged/sanctioned entity into the real-LEI graph (PR #45)."""

    def _real_graph_snaps(self) -> dict[str, EntitySnapshot]:
        # Two customers linked by a shared LEI so the graph has a real edge.
        return {
            "drift-002": _snap("drift-002", lei="LEI002", children=["LEI004"]),
            "drift-004": _snap("drift-004", lei="LEI004"),
        }

    def test_seed_node_added_and_linked_to_affected(self):
        g = build_graph_from_snapshots(
            self._real_graph_snaps(),
            sanctioned_seed="SANCTIONED_ENTITY",
            sanctioned_seed_name="Orion Capital Partners",
            contagion_affected={"drift-004", "drift-002"},
        )
        assert g is not None
        assert "SANCTIONED_ENTITY" in g.g
        assert g.g.nodes["SANCTIONED_ENTITY"]["name"] == "Orion Capital Partners"
        assert g.g.nodes["SANCTIONED_ENTITY"]["is_customer"] is False
        assert g.g.has_edge("SANCTIONED_ENTITY", "drift-004")
        assert g.g.has_edge("SANCTIONED_ENTITY", "drift-002")

    def test_contagion_propagates_from_seed_to_affected(self):
        g = build_graph_from_snapshots(
            self._real_graph_snaps(),
            sanctioned_seed="SANCTIONED_ENTITY",
            contagion_affected={"drift-004", "drift-002"},
        )
        assert g is not None
        result = g.propagate(["SANCTIONED_ENTITY"])
        assert result.propagated_risk["drift-004"] > 0.1
        assert result.propagated_risk["drift-002"] > 0.1

    def test_no_seed_when_no_affected_customer_present(self):
        # None of the affected ids resolve to a node → no orphan seed node.
        g = build_graph_from_snapshots(
            self._real_graph_snaps(),
            sanctioned_seed="SANCTIONED_ENTITY",
            contagion_affected={"drift-999"},
        )
        assert g is not None
        assert "SANCTIONED_ENTITY" not in g.g

    def test_default_no_seed_injection(self):
        # Without sanctioned_seed the graph is unchanged (backward compatible).
        g = build_graph_from_snapshots(self._real_graph_snaps())
        assert g is not None
        assert "SANCTIONED_ENTITY" not in g.g


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
