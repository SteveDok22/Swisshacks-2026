"""
DriftEngine — orchestrator for KYC drift detection.

Parallels the existing RiskEngine pattern. Combines the passive layers
(BOCPD behavioral drift, drift velocity, ownership contagion, deterministic
checks) and routes customers through the cost-aware cascade.

For the hackathon MVP, the customer book is the synthetic suite from
simulator.py (deterministic, ground-truth-labeled). In production this would
read from the bank's transaction store and registry feeds.

The engine is stateless across calls but caches the generated book so the
same customer IDs are stable within a process lifetime.
"""

from __future__ import annotations

import numpy as np

from app.drift.bocpd import BOCPD, standardize
from app.drift.cascade import CascadeRouter, CustomerSignal
from app.drift.contagion import build_demo_graph, OwnershipGraph
from app.drift.public_intel import (
    assess_public_risk,
    confirmation_lift,
    generate_signals_for_customer,
)
from app.drift.simulator import SyntheticCustomer, generate_book, generate_customer
from app.drift.velocity import compute_drift_series, velocity_band
from app.schemas.drift import (
    CascadeCostReport,
    ContagionGraph,
    DriftCustomerDetail,
    DriftCustomerSummary,
    DriftTimelinePoint,
    LayerContribution,
    PublicSignalOut,
)

# Sanctioned seed entity for the contagion demo
SANCTIONED_SEED = "SANCTIONED_ENTITY"
# Customers wired into the ownership graph as contagion-affected
CONTAGION_AFFECTED = {"drift-004", "drift-002"}


class DriftEngine:
    """Orchestrates drift detection over the customer book."""

    def __init__(self) -> None:
        self._book: list[SyntheticCustomer] = generate_book()
        self._router = CascadeRouter()
        self._graph: OwnershipGraph = build_demo_graph(
            [c.customer_id for c in self._book]
        )
        # Contagion is computed once (sanctions already hit in demo state)
        self._contagion = self._graph.propagate(seeds=[SANCTIONED_SEED])

    # ------------------------------------------------------------------ #
    # Core per-customer analysis
    # ------------------------------------------------------------------ #
    def _analyze_customer(self, cust: SyntheticCustomer) -> dict:
        """Run all passive layers for one customer. Returns raw signals.

        Two explicit layers, matching the AMINA Challenge 4 architecture:
          - PUBLIC INTELLIGENCE: external signals (news, sanctions, adverse
            media, ownership changes, funding events) -> public_risk
          - INTERNAL BANK DATA: BOCPD drift, velocity, ownership contagion
            -> internal_risk
        The two are fused, then amplified by Confirmation Lift when an
        external signal co-occurs in time with internal drift.
        """
        ds = compute_drift_series(cust.metric_windows())
        latest_velocity = ds.velocity[-1] if ds.velocity else 0.0
        max_velocity = max(ds.velocity) if ds.velocity else 0.0
        final_drift = ds.drift_bits[-1] if ds.drift_bits else 0.0

        # --- INTERNAL: BOCPD on daily volume ---
        daily = standardize(cust.daily_volume_series())
        bres = BOCPD(hazard=1 / 500).run(daily)
        cp_day = bres.detected_changepoints[0] if bres.detected_changepoints else None
        # Internal drift peak month (for temporal co-occurrence). Convert the
        # BOCPD day index to a month via days-per-month, else use velocity peak.
        if cp_day is not None and cust.monthly_volume:
            days_per_month = len(cust.monthly_volume[0]) or 21
            internal_peak_month = cp_day // days_per_month
        elif ds.velocity:
            internal_peak_month = ds.windows[int(np.argmax(ds.velocity))]
        else:
            internal_peak_month = None

        prop_risk = self._contagion.propagated_risk.get(cust.customer_id, 0.0)

        # Internal risk 0..1: velocity (leading) + accumulated drift + contagion
        vel_norm = min(max_velocity / 3.0, 1.0)
        drift_norm = min(final_drift / 20.0, 1.0)
        internal_risk = min(0.6 * vel_norm + 0.25 * drift_norm + 0.4 * prop_risk, 1.0)

        # --- PUBLIC: external signals ---
        signals = generate_signals_for_customer(
            cust.customer_id, cust.name, cust.scenario, months=cust.months,
            drift_start_month=cust.drift_start_month,
            seed=hash(cust.customer_id) % 9999,
        )
        pi = assess_public_risk(signals, months=cust.months)

        # --- Confirmation Lift: do the two worlds confirm each other? ---
        lift = confirmation_lift(
            pi.public_risk, internal_risk,
            pi.peak_signal_month, internal_peak_month,
        )

        # --- Fused score 0..100 ---
        # Base from the stronger of the two layers, then amplified by lift.
        base = max(internal_risk, pi.public_risk * 0.85)
        # Lift in [1, ~4]; map its excess over 1 into up to +35% amplification
        amplification = 1.0 + min((lift - 1.0) / 3.0, 1.0) * 0.35
        score = min(base * amplification * 100.0, 100.0)

        return {
            "drift_series": ds,
            "latest_velocity": latest_velocity,
            "max_velocity": max_velocity,
            "final_drift": final_drift,
            "bocpd_changepoint_day": cp_day,
            "propagated_risk": prop_risk,
            "internal_risk": internal_risk,
            "internal_peak_month": internal_peak_month,
            "public_signals": signals,
            "public_risk": pi.public_risk,
            "public_peak_month": pi.peak_signal_month,
            "confirmation_lift": lift,
            "drift_score": score,
        }

    def _build_layers(self, cust: SyntheticCustomer, analysis: dict) -> list[LayerContribution]:
        """Construct explainable per-layer contributions."""
        prop = analysis["propagated_risk"]
        max_vel = analysis["max_velocity"]
        final_drift = analysis["final_drift"]
        cp = analysis["bocpd_changepoint_day"]

        layers = [
            LayerContribution(
                layer=1, name="Deterministic (sanctions/PEP)",
                llr=0.0, status="ok",
                detail="No direct watchlist match",
            ),
            LayerContribution(
                layer=2, name="Public intelligence",
                llr=round(analysis["public_risk"] * 5, 2),
                status="deviation" if analysis["public_risk"] > 0.4 else (
                    "notable" if analysis["public_risk"] > 0.2 else "ok"
                ),
                detail=(
                    f"{len(analysis['public_signals'])} external signal(s), "
                    f"public risk {analysis['public_risk']:.2f}"
                    + (
                        f"; confirms internal drift (lift {analysis['confirmation_lift']:.1f}x)"
                        if analysis["confirmation_lift"] > 1.5 else ""
                    )
                    if analysis["public_signals"]
                    else "No external signals"
                ),
            ),
            LayerContribution(
                layer=3, name="Ownership contagion",
                llr=round(prop * 5, 2),
                status="deviation" if prop > 0.1 else "ok",
                detail=(
                    f"Propagated risk {prop:.2f} from sanctioned entity "
                    f"({self._contagion.hops_from_seed.get(cust.customer_id, '-')} hops)"
                    if prop > 0.01 else "No ownership path to flagged entities"
                ),
            ),
            LayerContribution(
                layer=4, name="Behavioral drift (BOCPD)",
                llr=round(min(max_vel, 5.0), 2),
                status="deviation" if cp is not None else "ok",
                detail=(
                    f"Regime change detected at day {cp}"
                    if cp is not None else "No regime change in transaction stream"
                ),
            ),
            LayerContribution(
                layer=5, name="Declared consistency / velocity",
                llr=round(min(final_drift / 5, 5.0), 2),
                status=velocity_band(max_vel) if max_vel > 0.3 else "ok",
                detail=f"Drift velocity peaked at {max_vel:.2f} bits/month",
            ),
        ]
        return layers

    # ------------------------------------------------------------------ #
    # Public API methods
    # ------------------------------------------------------------------ #
    def list_customers(self) -> list[DriftCustomerSummary]:
        out: list[DriftCustomerSummary] = []
        for cust in self._book:
            a = self._analyze_customer(cust)
            signal = CustomerSignal(
                customer_id=cust.customer_id,
                drift_score=a["drift_score"],
                propagated_risk=a["propagated_risk"],
            )
            decision = self._router.route_one(signal)
            out.append(
                DriftCustomerSummary(
                    customer_id=cust.customer_id,
                    name=cust.name,
                    drift_score=round(a["drift_score"], 1),
                    drift_velocity=round(a["max_velocity"], 3),
                    velocity_band=velocity_band(a["max_velocity"]),
                    reached_tier=decision.reached_tier.name,
                    sanctions_hit=False,
                    propagated_risk=round(a["propagated_risk"], 3),
                    public_risk=round(a["public_risk"], 3),
                    confirmation_lift=round(a["confirmation_lift"], 2),
                    scenario=cust.scenario,
                )
            )
        out.sort(key=lambda c: c.drift_score, reverse=True)
        return out

    def get_customer(self, customer_id: str) -> DriftCustomerDetail | None:
        cust = next((c for c in self._book if c.customer_id == customer_id), None)
        if cust is None:
            return None
        a = self._analyze_customer(cust)
        ds = a["drift_series"]

        signal = CustomerSignal(
            customer_id=cust.customer_id,
            drift_score=a["drift_score"],
            propagated_risk=a["propagated_risk"],
        )
        decision = self._router.route_one(signal)

        timeline = [
            DriftTimelinePoint(
                month=ds.windows[i],
                drift_bits=round(ds.drift_bits[i], 3),
                velocity=round(ds.velocity[i], 3),
                acceleration=round(ds.acceleration[i], 3),
                bocpd_changepoint=False,
            )
            for i in range(len(ds.windows))
        ]

        return DriftCustomerDetail(
            customer_id=cust.customer_id,
            name=cust.name,
            drift_score=round(a["drift_score"], 1),
            drift_velocity=round(a["max_velocity"], 3),
            velocity_band=velocity_band(a["max_velocity"]),
            reached_tier=decision.reached_tier.name,
            escalation_reasons=decision.escalation_reasons,
            layers=self._build_layers(cust, a),
            timeline=timeline,
            scenario=cust.scenario,
            drift_start_month=cust.drift_start_month,
            sanctions_month=cust.sanctions_month,
            bocpd_changepoint_day=a["bocpd_changepoint_day"],
            public_risk=round(a["public_risk"], 3),
            internal_risk=round(a["internal_risk"], 3),
            confirmation_lift=round(a["confirmation_lift"], 2),
            public_signals=[
                PublicSignalOut(**s.to_dict()) for s in a["public_signals"]
            ],
        )

    def scan(self) -> CascadeCostReport:
        """Run full cascade over the book, return cost report."""
        signals = []
        for cust in self._book:
            a = self._analyze_customer(cust)
            signals.append(
                CustomerSignal(
                    customer_id=cust.customer_id,
                    drift_score=a["drift_score"],
                    propagated_risk=a["propagated_risk"],
                )
            )
        report = self._router.route_book(signals)
        llm_all = len(signals) * 0.05
        savings = 100.0 * (1 - report.total_cost / llm_all) if llm_all > 0 else 0.0
        return CascadeCostReport(
            total_customers=report.total_customers,
            tier_counts=report.tier_counts,
            tier_costs={k: round(v, 4) for k, v in report.tier_costs.items()},
            total_cost=round(report.total_cost, 2),
            summary=report.summary_line(),
            llm_on_everything_cost=round(llm_all, 2),
            savings_pct=round(savings, 1),
        )

    def contagion_graph(self) -> ContagionGraph:
        data = self._graph.to_cytoscape(self._contagion)
        return ContagionGraph(
            nodes=data["nodes"],
            edges=data["edges"],
            seeds=self._contagion.seeds,
        )

    def inject_scenario(self, scenario: str, name: str) -> DriftCustomerDetail:
        """Red-team: add a synthetic customer with a chosen drift scenario."""
        new_id = f"injected-{len(self._book) + 1:03d}"
        cust = generate_customer(
            customer_id=new_id, name=name, scenario=scenario,
            seed=hash(new_id) % 10000,
        )
        self._book.append(cust)
        detail = self.get_customer(new_id)
        assert detail is not None
        return detail


# Process-level singleton (book is stable within a run)
_engine: DriftEngine | None = None


def get_drift_engine() -> DriftEngine:
    global _engine
    if _engine is None:
        _engine = DriftEngine()
    return _engine
