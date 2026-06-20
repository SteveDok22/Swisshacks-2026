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

import json
from typing import Any

import numpy as np

from app.drift.bocpd import BOCPD, standardize
from app.drift.cascade import CascadeRouter, CustomerSignal, Tier
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
from app.ml.base import score_to_level
from app.schemas.drift import (
    CascadeCostReport,
    CausalVerdictOut,
    ContagionGraph,
    DormancyOut,
    DriftSubjectDetail,
    DriftSubjectSummary,
    DriftTimelinePoint,
    LayerContribution,
    PublicSignalOut,
    StabilityOut,
    AsOfPointOut,
    ReplayResult,
)
from app.schemas.enums import DecisionAction
from app.services.anthropic_client import get_anthropic_client


T2_LLM_SYSTEM_MESSAGE = (
    "You are a careful AML/KYC compliance analyst. Return valid JSON only. "
    "Do not invent facts. Use only the provided evidence. Do not recommend "
    "automatic account blocking. Recommend human compliance actions only."
)

LLM_PARSE_FALLBACK = {
    "verdict": "ambiguous",
    "confidence": 0.0,
    "rationale": "LLM response could not be parsed as valid JSON.",
    "key_evidence": [],
    "recommended_action": "Request information",
}

# Sanctioned seed entity for the contagion demo
SANCTIONED_SEED = "SANCTIONED_ENTITY"
# Customers wired into the ownership graph as contagion-affected
CONTAGION_AFFECTED = {"drift-004", "drift-002"}
DRIFT_ANALYSIS_VERSION = "drift-v1"


def recommend_drift_action(
    score: float,
    causal_label: str,
    is_suspicious: bool,
) -> DecisionAction:
    """Single authoritative mapping used by API responses and decisions."""
    if is_suspicious:
        return DecisionAction.ESCALATE
    if causal_label == "benign":
        return DecisionAction.ALLOW
    if score >= 70 or causal_label == "risk":
        return DecisionAction.ESCALATE
    if score >= 40 or causal_label == "ambiguous":
        return DecisionAction.STEP_UP_VERIFICATION
    return DecisionAction.ALLOW


class DriftEngine:
    """Orchestrates drift detection over the customer book."""

    def __init__(self) -> None:
        self._book: list[SyntheticCustomer] = generate_book()
        self._router = CascadeRouter()
        self._graph: OwnershipGraph = build_demo_graph(
            [c.drift_id for c in self._book]
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
        # Map the BOCPD changepoint (a day index over the concatenated daily
        # series) to its month window. Computed once here and reused for both
        # the temporal co-occurrence signal and the timeline marker.
        cp_month = cust.day_to_month(cp_day) if cp_day is not None else None
        # Internal drift peak month (for temporal co-occurrence): the changepoint
        # month if we have one, else the velocity peak.
        if cp_month is not None:
            internal_peak_month = cp_month
        elif ds.velocity:
            internal_peak_month = ds.windows[int(np.argmax(ds.velocity))]
        else:
            internal_peak_month = None

        prop_risk = self._contagion.propagated_risk.get(cust.drift_id, 0.0)

        # Internal risk 0..1: velocity (leading) + accumulated drift + contagion
        vel_norm = min(max_velocity / 3.0, 1.0)
        drift_norm = min(final_drift / 20.0, 1.0)
        internal_risk = min(0.6 * vel_norm + 0.25 * drift_norm + 0.4 * prop_risk, 1.0)

        # --- PUBLIC: external signals ---
        signals = generate_signals_for_customer(
            cust.drift_id, cust.name, cust.scenario, months=cust.months,
            drift_start_month=cust.drift_start_month,
            seed=hash(cust.drift_id) % 9999,
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
        # NOTE: this floor is applied AFTER the causal demotion above and will
        # override it on purpose — a reactivated shell must surface even if the
        # causal layer reads the new activity as (so far) benign-shaped. This is
        # the same "cannot hide below the radar" policy as the stability floor.
        if dormancy.is_dormancy_break:
            score = max(score, 55.0 + dormancy.dormancy_break * 35.0)

        return {
            "drift_series": ds,
            "latest_velocity": latest_velocity,
            "max_velocity": max_velocity,
            "final_drift": final_drift,
            "bocpd_changepoint_day": cp_day,
            "bocpd_changepoint_month": cp_month,
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
                    f"({self._contagion.hops_from_seed.get(cust.drift_id, '-')} hops)"
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

    def _build_t2_adjudication_prompt(
        self,
        cust: SyntheticCustomer,
        analysis: dict,
    ) -> str:
        """Build a strict JSON-only adjudication prompt for T2 cases."""
        causal = analysis["causal"]
        stability = analysis["stability"]
        dormancy = analysis["dormancy"]
        signature = causal.signature
        context: dict[str, Any] = {
            "customer": {
                "id": cust.drift_id,
                "name": cust.name,
                "scenario": cust.scenario,
            },
            "risk_scores": {
                "drift_score": round(analysis["drift_score"], 3),
                "internal_risk": round(analysis["internal_risk"], 3),
                "public_risk": round(analysis["public_risk"], 3),
                "confirmation_lift": round(analysis["confirmation_lift"], 3),
                "propagated_risk": round(analysis["propagated_risk"], 3),
            },
            "causal_assessment": {
                "label": causal.label,
                "p_risk": round(causal.p_risk, 3),
                "causal_likelihood_ratio": round(causal.causal_llr, 3),
                "contributions": {
                    k: round(v, 3) for k, v in causal.contributions.items()
                },
            },
            "drift_signature": {
                "volume_change": round(signature.volume_change, 3),
                "margin_change": round(signature.margin_change, 3),
                "counterparty_risk_change": round(signature.counterparty_change, 3),
                "corridor_risk_change": round(signature.corridor_change, 3),
            },
            "suspicious_stability": {
                "is_suspicious": stability.is_suspicious,
                "score": round(stability.suspicion, 3),
                "detail": stability.detail,
            },
            "dormancy_break": {
                "is_dormancy_break": dormancy.is_dormancy_break,
                "score": round(dormancy.dormancy_break, 3),
                "baseline_volume": round(dormancy.baseline_volume, 1),
                "active_volume": round(dormancy.active_volume, 1),
                "detail": dormancy.detail,
            },
            "public_signals": [
                {
                    "type": signal.signal_type,
                    "headline": signal.headline,
                    "severity": round(signal.severity, 3),
                    "source": signal.source,
                    "month": signal.month,
                }
                for signal in analysis["public_signals"]
            ],
        }

        return (
            "Adjudicate this T2 KYC drift case by comparing three hypotheses:\n"
            "1. Risk-shaped or causal drift hypothesis.\n"
            "2. Benign business-change hypothesis.\n"
            "3. Ambiguous or insufficient-evidence hypothesis.\n\n"
            "Use only the structured evidence below. Do not invent facts. "
            "Do not recommend automatic blocking; recommend human compliance "
            "actions such as enhanced due diligence, request for information, "
            "monitoring, or no immediate action.\n\n"
            "Structured evidence:\n"
            f"{json.dumps(context, indent=2, sort_keys=True)}\n\n"
            "Return JSON only with this exact shape:\n"
            "{\n"
            '  "verdict": "risk" | "benign" | "ambiguous",\n'
            '  "confidence": number,\n'
            '  "rationale": string,\n'
            '  "key_evidence": string[],\n'
            '  "recommended_action": string\n'
            "}"
        )

    def _parse_llm_json(self, text: str) -> dict[str, Any]:
        """Parse and normalize a T2 adjudication JSON response defensively."""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return dict(LLM_PARSE_FALLBACK)
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return dict(LLM_PARSE_FALLBACK)

        if not isinstance(payload, dict):
            return dict(LLM_PARSE_FALLBACK)

        verdict = payload.get("verdict")
        if verdict not in {"risk", "benign", "ambiguous"}:
            verdict = "ambiguous"

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(max(confidence, 0.0), 1.0)

        key_evidence = payload.get("key_evidence", [])
        if not isinstance(key_evidence, list):
            key_evidence = []
        key_evidence = [str(item) for item in key_evidence]

        rationale = payload.get("rationale", "")
        recommended_action = payload.get("recommended_action", "Request information")

        return {
            "verdict": verdict,
            "confidence": confidence,
            "rationale": str(rationale),
            "key_evidence": key_evidence,
            "recommended_action": str(recommended_action),
        }

    def _run_t2_llm_adjudication(
        self,
        cust: SyntheticCustomer,
        analysis: dict,
    ) -> dict[str, Any]:
        """Execute the real or mock Anthropic T2 adjudication path."""
        llm = get_anthropic_client()
        llm_mode = "mock" if llm.is_mock else "real"
        text, was_cached = llm.complete(
            self._build_t2_adjudication_prompt(cust, analysis),
            system=T2_LLM_SYSTEM_MESSAGE,
            max_tokens=700,
        )

        return {
            "drift_id": cust.drift_id,
            "drift_name": cust.name,
            "llm_mode": llm_mode,
            "was_cached": was_cached,
            "response": self._parse_llm_json(text),
        }

    # ------------------------------------------------------------------ #
    # Public API methods
    # ------------------------------------------------------------------ #
    def list_customers(self) -> list[DriftSubjectSummary]:
        out: list[DriftSubjectSummary] = []
        for cust in self._book:
            a = self._analyze_customer(cust)
            signal = CustomerSignal(
                drift_id=cust.drift_id,
                drift_score=a["drift_score"],
                propagated_risk=a["propagated_risk"],
            )
            decision = self._router.route_one(signal)
            out.append(
                DriftSubjectSummary(
                    drift_id=cust.drift_id,
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
                    dormancy_break=round(a["dormancy"].dormancy_break, 3),
                    is_dormancy_break=a["dormancy"].is_dormancy_break,
                    scenario=cust.scenario,
                )
            )
        out.sort(key=lambda c: c.drift_score, reverse=True)
        return out

    def get_customer(self, drift_id: str) -> DriftSubjectDetail | None:
        cust = next((c for c in self._book if c.drift_id == drift_id), None)
        if cust is None:
            return None
        a = self._analyze_customer(cust)
        ds = a["drift_series"]

        signal = CustomerSignal(
            drift_id=cust.drift_id,
            drift_score=a["drift_score"],
            propagated_risk=a["propagated_risk"],
        )
        decision = self._router.route_one(signal)
        recommended_action = recommend_drift_action(
            a["drift_score"],
            a["causal"].label,
            a["stability"].is_suspicious,
        )

        # Mark the timeline point at the BOCPD changepoint month (mapped from a
        # day index in _analyze_customer). A changepoint that lands in the
        # baseline window — before the first timeline point — matches no point
        # and is correctly left unmarked, as is the no-changepoint (None) case.
        cp_month = a["bocpd_changepoint_month"]

        timeline = [
            DriftTimelinePoint(
                month=ds.windows[i],
                drift_bits=round(ds.drift_bits[i], 3),
                velocity=round(ds.velocity[i], 3),
                acceleration=round(ds.acceleration[i], 3),
                bocpd_changepoint=ds.windows[i] == cp_month,
            )
            for i in range(len(ds.windows))
        ]

        return DriftSubjectDetail(
            drift_id=cust.drift_id,
            name=cust.name,
            drift_score=round(a["drift_score"], 1),
            drift_velocity=round(a["max_velocity"], 3),
            velocity_band=velocity_band(a["max_velocity"]),
            reached_tier=decision.reached_tier.name,
            recommended_action=recommended_action,
            risk_level=score_to_level(a["drift_score"]),
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
            dormancy=DormancyOut(
                dormancy_break=round(a["dormancy"].dormancy_break, 3),
                dormancy_depth=round(a["dormancy"].dormancy_depth, 3),
                activation_strength=round(a["dormancy"].activation_strength, 3),
                baseline_volume=round(a["dormancy"].baseline_volume, 1),
                active_volume=round(a["dormancy"].active_volume, 1),
                is_dormancy_break=a["dormancy"].is_dormancy_break,
                detail=a["dormancy"].detail,
            ),
        )

    def scan(self) -> CascadeCostReport:
        """Run full cascade over the book, return cost report."""
        signals = []
        analyses: dict[str, tuple[SyntheticCustomer, dict]] = {}
        for cust in self._book:
            a = self._analyze_customer(cust)
            analyses[cust.drift_id] = (cust, a)
            signals.append(
                CustomerSignal(
                    drift_id=cust.drift_id,
                    drift_score=a["drift_score"],
                    propagated_risk=a["propagated_risk"],
                )
            )
        report = self._router.route_book(signals)
        llm_adjudications = []
        for decision in report.decisions:
            if decision.reached_tier != Tier.T2_LLM:
                continue
            cust, analysis = analyses[decision.drift_id]
            llm_adjudications.append(
                self._run_t2_llm_adjudication(cust, analysis)
            )

        actual_t2_llm_calls = len(llm_adjudications)
        real_t2_llm_calls = sum(
            1 for item in llm_adjudications if item["llm_mode"] == "real"
        )
        mock_t2_llm_calls = sum(
            1 for item in llm_adjudications if item["llm_mode"] == "mock"
        )
        llm_all = len(signals) * 0.05
        savings = 100.0 * (1 - report.total_cost / llm_all) if llm_all > 0 else 0.0
        summary = (
            f"{report.summary_line()}. Actual T2 LLM adjudications: "
            f"{actual_t2_llm_calls} total, {real_t2_llm_calls} real, "
            f"{mock_t2_llm_calls} mock."
        )
        return CascadeCostReport(
            total_customers=report.total_customers,
            tier_counts=report.tier_counts,
            tier_costs={k: round(v, 4) for k, v in report.tier_costs.items()},
            total_cost=round(report.total_cost, 2),
            summary=summary,
            llm_on_everything_cost=round(llm_all, 2),
            savings_pct=round(savings, 1),
            actual_t2_llm_calls=actual_t2_llm_calls,
            real_t2_llm_calls=real_t2_llm_calls,
            mock_t2_llm_calls=mock_t2_llm_calls,
            llm_adjudications=llm_adjudications,
        )

    def contagion_graph(self) -> ContagionGraph:
        data = self._graph.to_cytoscape(self._contagion)
        return ContagionGraph(
            nodes=data["nodes"],
            edges=data["edges"],
            seeds=self._contagion.seeds,
        )

    def replay(self, drift_id: str) -> ReplayResult | None:
        """Time-Travel Audit: as-of replay proving no look-ahead bias."""
        cust = next((c for c in self._book if c.drift_id == drift_id), None)
        if cust is None:
            return None

        prop = self._contagion.propagated_risk.get(drift_id, 0.0)
        # The seed entity is sanctioned at the customer's sanctions_month;
        # before that, contagion risk does not exist (no look-ahead).
        listing_month = cust.sanctions_month

        traj = replay_trajectory(
            cust,
            propagated_risk_final=prop,
            contagion_listing_month=listing_month,
        )

        return ReplayResult(
            drift_id=cust.drift_id,
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

    def inject_scenario(self, scenario: str, name: str) -> DriftSubjectDetail:
        """Red-team: add a synthetic customer with a chosen drift scenario."""
        new_id = f"injected-{len(self._book) + 1:03d}"
        cust = generate_customer(
            drift_id=new_id, name=name, scenario=scenario,
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
