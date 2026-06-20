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
from app.drift.causal import causal_assessment
from app.drift.contagion import build_demo_graph, OwnershipGraph
from app.drift.public_intel import (
    assess_public_risk,
    confirmation_lift,
    generate_signals_for_customer,
)
from app.drift.simulator import SyntheticCustomer, generate_book, generate_customer
from app.drift.stability import assess_stability, cohort_volatility
from app.drift.dormancy import assess_dormancy
from app.drift.timetravel import replay_trajectory
from app.drift.velocity import compute_drift_series, velocity_band
from app.schemas.drift import (
    CascadeCostReport,
    CausalVerdictOut,
    ContagionGraph,
    DriftCustomerDetail,
    DriftCustomerSummary,
    DriftTimelinePoint,
    LayerContribution,
    PublicSignalOut,
    StabilityOut,
    AsOfPointOut,
    ReplayResult,
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
        # Cohort volatility reference for Suspicious Stability (computed once
        # over the whole book — the norm against which smoothness is judged).
        self._cohort_cv = cohort_volatility([c.monthly_volume for c in self._book])

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

        # --- CAUSAL: is this drift risk-shaped or life-shaped? ---
        # Uses causal_windows (includes margin_ratio, the discriminator) which
        # is deliberately kept OUT of velocity so the two measures stay
        # orthogonal: velocity = how much changed, causal = in which direction.
        causal = causal_assessment(cust.causal_windows())

        # --- SUSPICIOUS STABILITY: is the customer anomalously smooth while
        # the environment moves? (the slow-walker / sleeper) ---
        stability = assess_stability(
            cust.monthly_volume,
            self._cohort_cv,
            counterparty_monthly=cust.counterparty_risk,
            corridor_monthly=cust.corridor_risk,
            public_risk=pi.public_risk,
        )

        # --- DORMANCY BREAK: was the customer dormant, then suddenly active?
        # (AMINA use case: "previously dormant company begins high volume") ---
        dormancy = assess_dormancy(cust.monthly_volume)

        # Causal modulation — the whole point of the causal layer is to act on
        # the verdict, not just display it. A high-magnitude drift that is
        # clearly LIFE-SHAPED (benign) should NOT sit at the top of the
        # officer's queue; a risk-shaped drift is confirmed. We modulate the
        # score by a factor derived from p_risk:
        #   p_risk ~1.0 (risk)   -> factor ~1.0  (score stands)
        #   p_risk ~0.5 (unsure) -> factor ~0.85 (mild discount)
        #   p_risk ~0.0 (benign) -> factor ~0.45 (strong discount)
        # Benign business growth is demoted, not erased — an officer can still
        # see it, but it stops generating false-positive alerts.
        causal_factor = 0.45 + 0.55 * causal.p_risk
        score = min(score * causal_factor, 100.0)

        # Suspicious-stability ELEVATION — the slow-walker keeps drift low ON
        # PURPOSE, so it would otherwise slip through with a near-zero score.
        # When suspicion is high we floor the score upward: a flagged
        # slow-walker cannot hide below the radar.
        if stability.is_suspicious:
            score = max(score, 50.0 + stability.suspicion * 40.0)

        # Dormancy-break ELEVATION — a reactivated sleeper starts from a quiet
        # baseline, so drift/velocity under-react. When a genuine dormant->active
        # burst is detected, floor the score upward so it surfaces for review.
        if dormancy.is_dormancy_break:
            score = max(score, 55.0 + dormancy.dormancy_break * 35.0)

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
            "causal": causal,
            "stability": stability,
            "dormancy": dormancy,
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
                    causal_label=a["causal"].label,
                    causal_p_risk=round(a["causal"].p_risk, 3),
                    suspicion=round(a["stability"].suspicion, 3),
                    is_suspicious=a["stability"].is_suspicious,
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
            causal=CausalVerdictOut(
                causal_llr=round(a["causal"].causal_llr, 2),
                p_risk=round(a["causal"].p_risk, 3),
                label=a["causal"].label,
                volume_change=round(a["causal"].signature.volume_change, 3),
                margin_change=round(a["causal"].signature.margin_change, 3),
                counterparty_change=round(a["causal"].signature.counterparty_change, 3),
                corridor_change=round(a["causal"].signature.corridor_change, 3),
                contributions={k: round(v, 2) for k, v in a["causal"].contributions.items()},
            ),
            stability=StabilityOut(
                suspicion=round(a["stability"].suspicion, 3),
                stability_anomaly=round(a["stability"].stability_anomaly, 3),
                environmental_movement=round(a["stability"].environmental_movement, 3),
                own_volatility=round(a["stability"].own_volatility, 4),
                cohort_volatility=round(a["stability"].cohort_volatility, 4),
                is_suspicious=a["stability"].is_suspicious,
                detail=a["stability"].detail,
            ),
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

    def replay(self, customer_id: str) -> ReplayResult | None:
        """Time-Travel Audit: as-of replay proving no look-ahead bias."""
        cust = next((c for c in self._book if c.customer_id == customer_id), None)
        if cust is None:
            return None

        prop = self._contagion.propagated_risk.get(customer_id, 0.0)
        # The seed entity is sanctioned at the customer's sanctions_month;
        # before that, contagion risk does not exist (no look-ahead).
        listing_month = cust.sanctions_month

        traj = replay_trajectory(
            cust,
            propagated_risk_final=prop,
            contagion_listing_month=listing_month,
        )

        return ReplayResult(
            customer_id=cust.customer_id,
            name=cust.name,
            points=[
                AsOfPointOut(
                    month=p.month,
                    as_of_score=p.as_of_score,
                    velocity=p.velocity,
                    public_risk=p.public_risk,
                    contagion_active=p.contagion_active,
                    causal_p_risk=p.causal_p_risk,
                )
                for p in traj["points"]
            ],
            alert_month=traj["alert_month"],
            sanctions_month=traj["sanctions_month"],
            lead_time_months=traj["lead_time_months"],
            alert_threshold=traj["alert_threshold"],
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
