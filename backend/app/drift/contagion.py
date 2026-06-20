"""
Risk contagion through ownership topology (Layer 3).

When an entity becomes flagged (sanctions, adverse media), risk propagates
through the ownership graph to connected customers — often BEFORE any list
contains the connected customer's own name.

Method: personalized PageRank (Page et al. 1999) with the personalization
vector concentrated on the newly flagged "seed" entities. Customers a few
ownership hops away from a sanctioned entity receive elevated propagated
risk proportional to the strength and proximity of the connection.

This is the demo moment no "news API + LLM" team can show: a node lights up
red, and the risk wave visibly propagates across ownership links to bank
customers who are themselves on no list.

Pure NetworkX. ~140 lines.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import networkx as nx

from app.sources.base import EntitySnapshot


@dataclass
class OwnershipEdge:
    """A directed ownership relation: `owner` holds a stake in `target`."""

    owner: str
    target: str
    stake: float  # 0..1 ownership fraction


@dataclass
class ContagionResult:
    """Output of a contagion pass."""

    # entity id -> propagated risk score (0..1, normalized)
    propagated_risk: dict[str, float]
    # customers (subset of nodes) sorted by propagated risk, descending
    ranked_customers: list[tuple[str, float]]
    # the seed entities that triggered propagation
    seeds: list[str]
    # shortest-path hop distance from any seed (for UI / explanation)
    hops_from_seed: dict[str, int] = field(default_factory=dict)


class OwnershipGraph:
    """
    Directed ownership graph with personalized-PageRank risk contagion.

    Nodes are entities (companies, trusts, individuals). A subset of nodes
    are bank customers (flagged via `is_customer`). Edges carry ownership
    stake as weight.
    """

    def __init__(self) -> None:
        self.g = nx.DiGraph()

    def add_entity(
        self,
        entity_id: str,
        *,
        name: str | None = None,
        is_customer: bool = False,
        entity_type: str = "company",
    ) -> None:
        self.g.add_node(
            entity_id,
            name=name or entity_id,
            is_customer=is_customer,
            entity_type=entity_type,
        )

    def add_ownership(self, owner: str, target: str, stake: float) -> None:
        """Owner holds `stake` fraction of target."""
        self.g.add_edge(owner, target, stake=float(stake))

    def add_edges(self, edges: list[OwnershipEdge]) -> None:
        for e in edges:
            self.add_ownership(e.owner, e.target, e.stake)

    def customers(self) -> list[str]:
        return [n for n, d in self.g.nodes(data=True) if d.get("is_customer")]

    def propagate(
        self,
        seeds: list[str],
        *,
        alpha: float = 0.85,
    ) -> ContagionResult:
        """
        Propagate risk from `seeds` using personalized PageRank.

        Risk flows along ownership edges in BOTH directions of concern:
        - downstream: a sanctioned owner contaminates what it owns
        - upstream: owning a sanctioned entity contaminates the owner

        We run PageRank on an undirected view weighted by stake, which
        captures both directions. `alpha` is the damping (teleport) factor.
        """
        seeds = [s for s in seeds if s in self.g]
        if not seeds:
            return ContagionResult(propagated_risk={}, ranked_customers=[], seeds=[])

        # Personalization vector concentrated on seeds
        personalization = dict.fromkeys(self.g.nodes, 0.0)
        for s in seeds:
            personalization[s] = 1.0 / len(seeds)

        # Undirected, stake-weighted view for symmetric contamination
        undirected = self.g.to_undirected()
        ppr = nx.pagerank(
            undirected,
            alpha=alpha,
            personalization=personalization,
            weight="stake",
        )

        # Normalize to 0..1 by the max (seeds will be highest)
        max_score = max(ppr.values()) if ppr else 1.0
        if max_score <= 0:
            max_score = 1.0
        propagated = {n: v / max_score for n, v in ppr.items()}

        # Hop distance from nearest seed (for explanation)
        hops: dict[str, int] = {}
        for seed in seeds:
            lengths = nx.single_source_shortest_path_length(undirected, seed)
            for node, d in lengths.items():
                hops[node] = min(hops.get(node, 10**9), d)

        # Rank customers (exclude seeds themselves)
        ranked = sorted(
            (
                (n, propagated[n])
                for n in self.customers()
                if n not in seeds
            ),
            key=lambda kv: kv[1],
            reverse=True,
        )

        return ContagionResult(
            propagated_risk=propagated,
            ranked_customers=ranked,
            seeds=seeds,
            hops_from_seed=hops,
        )

    def to_cytoscape(self, contagion: ContagionResult | None = None) -> dict:
        """
        Export graph as nodes/edges for frontend visualization.
        If `contagion` provided, attach propagated risk to each node.
        """
        risk = contagion.propagated_risk if contagion else {}
        hops = contagion.hops_from_seed if contagion else {}
        seeds = set(contagion.seeds) if contagion else set()

        nodes = []
        for n, d in self.g.nodes(data=True):
            nodes.append(
                {
                    "id": n,
                    "name": d.get("name", n),
                    "is_customer": d.get("is_customer", False),
                    "entity_type": d.get("entity_type", "company"),
                    "risk": round(risk.get(n, 0.0), 4),
                    "hops_from_seed": hops.get(n),
                    "is_seed": n in seeds,
                }
            )
        edges = [
            {"source": u, "target": v, "stake": d.get("stake", 0.0)}
            for u, v, d in self.g.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}


def build_demo_graph(drift_ids: list[str]) -> OwnershipGraph:
    """
    Construct a demo ownership graph that connects some bank customers to a
    shell-company structure, which in turn connects to an entity that will
    later be sanctioned.

    Topology (designed for the contagion demo):

        SANCTIONED_ENTITY  (the seed, flagged at month 0)
              |
        ShellCo_Alpha  ---- owns ---->  drift-004 (Sergei, combined drift)
              |
        ShellCo_Beta   ---- owns ---->  drift-002 (Helena, counterparty)
              |
        CleanHolding   ---- owns ---->  drift-005 (stable, should stay low)

    So when SANCTIONED_ENTITY is flagged, Sergei and Helena light up via
    propagation (2 hops), while distant stable customers do not.
    """
    g = OwnershipGraph()

    # The entity that gets sanctioned
    g.add_entity("SANCTIONED_ENTITY", name="Orion Capital Partners", entity_type="company")

    # Shell layer
    g.add_entity("ShellCo_Alpha", name="Alpha Holdings SA", entity_type="shell")
    g.add_entity("ShellCo_Beta", name="Beta Ventures Ltd", entity_type="shell")
    g.add_entity("CleanHolding", name="Helvetia Trust AG", entity_type="company")

    # Customers (link a few of our synthetic drift customers)
    for cid in drift_ids:
        g.add_entity(cid, name=cid, is_customer=True, entity_type="individual")

    # Ownership edges (owner -> target, stake)
    g.add_ownership("SANCTIONED_ENTITY", "ShellCo_Alpha", 0.6)
    g.add_ownership("SANCTIONED_ENTITY", "ShellCo_Beta", 0.4)

    # Connect the high-drift customers through the shells
    if "drift-004" in drift_ids:
        g.add_ownership("ShellCo_Alpha", "drift-004", 0.3)
    if "drift-002" in drift_ids:
        g.add_ownership("ShellCo_Beta", "drift-002", 0.25)

    # A clean holding owning a stable customer (control)
    g.add_ownership("CleanHolding", "drift-005", 0.5) if "drift-005" in drift_ids else None

    return g


# GLEIF's relationship endpoints expose the existence of a parent/child link but
# not the numeric ownership fraction. We default both edge stakes to a neutral
# mid weight so PageRank contagion still flows along real links; refine once a
# source carrying actual stake percentages (e.g. OpenCorporates) is wired in.
_GLEIF_PARENT_STAKE = 0.5
_GLEIF_CHILD_STAKE = 0.5

# Stake for the injected sanctioned-seed → affected-customer edge in a real-LEI
# graph. GLEIF carries no flag/sanction data, so the demo seeds a known flagged
# entity into the live graph the same way build_demo_graph does for the
# synthetic one; a neutral mid weight lets PageRank contagion flow along it.
_GLEIF_SEED_STAKE = 0.5


def build_graph_from_snapshots(
    snapshots: dict[str, EntitySnapshot],
    *,
    sanctioned_seed: str | None = None,
    sanctioned_seed_name: str | None = None,
    contagion_affected: Iterable[str] = (),
    seed_stake: float = _GLEIF_SEED_STAKE,
) -> OwnershipGraph | None:
    """
    Build an ownership graph from real GLEIF ``EntitySnapshot``s (Use case 3).

    Each snapshot is one bank customer keyed by ``drift_id``. The GLEIF adapter
    stores the ultimate-parent LEI in ``beneficial_owners`` (entity-level UBO
    proxy) and the direct-child LEIs in ``officers`` (subsidiary nodes), with the
    customer's own LEI in ``raw_data["lei"]``. We add each customer as a graph
    node and link it to its parent/child LEI nodes via ownership edges. When a
    parent/child LEI matches another customer's own LEI, the edge connects the
    two customers directly so risk contagion can flow across the book.

    Returns ``None`` when no snapshot carries any ownership link — the caller
    then falls back to :func:`build_demo_graph`. This is the real-LEI replacement
    for the synthetic contagion graph.

    When ``sanctioned_seed`` is given, a flagged/sanctioned entity is injected
    into the real-LEI graph and linked to each ``contagion_affected`` customer
    that resolved to a node, so contagion can propagate over live LEIs exactly as
    it does in :func:`build_demo_graph` (PR #45 follow-up). The seed is only added
    when at least one affected customer is present, so it never leaves an orphan
    node, and only after a real ownership graph has been confirmed (the
    edge-count gate below still decides the demo fallback).
    """
    if not snapshots:
        return None

    # Map every customer's own LEI to its drift_id so a parent/child LEI that
    # belongs to another customer in the book resolves to that customer's node
    # (a shared node) rather than a duplicate external one.
    lei_to_drift_id: dict[str, str] = {}
    for drift_id, snap in snapshots.items():
        lei = snap.raw_data.get("lei")
        if lei:
            lei_to_drift_id[lei] = drift_id

    g = OwnershipGraph()
    for drift_id, snap in snapshots.items():
        g.add_entity(
            drift_id,
            name=snap.name or drift_id,
            is_customer=True,
            entity_type="company",
        )

    def _resolve(lei: str) -> str:
        """Map a LEI to a book customer's node, or add it as an external node."""
        node = lei_to_drift_id.get(lei, lei)
        if node not in g.g:
            g.add_entity(node, name=lei, is_customer=False, entity_type="company")
        return node

    edge_count = 0
    for drift_id, snap in snapshots.items():
        # Ultimate parent owns the customer (parent -> customer).
        for parent_lei in snap.beneficial_owners:
            parent = _resolve(parent_lei)
            if parent == drift_id:
                continue  # ignore a self-referential parent
            g.add_ownership(parent, drift_id, _GLEIF_PARENT_STAKE)
            edge_count += 1
        # Customer owns each direct child (customer -> child).
        for child_lei in snap.officers:
            child = _resolve(child_lei)
            if child == drift_id:
                continue
            g.add_ownership(drift_id, child, _GLEIF_CHILD_STAKE)
            edge_count += 1

    if edge_count == 0:
        return None

    # Overlay the flagged seed onto the confirmed real-LEI graph so contagion
    # has a sanctioned origin to propagate from (mirrors build_demo_graph). Only
    # link affected customers that actually resolved to a node, and skip the
    # whole step when none are present so we never add an isolated seed node.
    if sanctioned_seed is not None:
        present_affected = [
            cid for cid in contagion_affected if cid in g.g and cid != sanctioned_seed
        ]
        if present_affected:
            g.add_entity(
                sanctioned_seed,
                name=sanctioned_seed_name or sanctioned_seed,
                is_customer=False,
                entity_type="company",
            )
            for cid in present_affected:
                g.add_ownership(sanctioned_seed, cid, seed_stake)

    return g
