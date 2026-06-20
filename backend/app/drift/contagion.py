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

from dataclasses import dataclass, field

import networkx as nx


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
        personalization = {n: 0.0 for n in self.g.nodes}
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
