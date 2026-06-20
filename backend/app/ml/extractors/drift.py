"""
Feature extractor for KYC drift detection.

Extracts a 20-dimensional feature vector from a drift analysis dict,
capturing all engine layers: velocity, BOCPD changepoint, causal signature,
suspicious stability, and dormancy break.

Consumed by DriftEngine._analyze_customer() after the heuristic pipeline runs.
The XGBoost model trained on these features adds a data-driven complement to
the hand-tuned layer weights.
"""

from __future__ import annotations

from typing import Any

from app.ml.base import FeatureExtractor
from app.schemas.case import Case


class DriftFeatureExtractor(FeatureExtractor):
    """Extract 20-dim features from a drift analysis dict for XGBoost scoring."""

    feature_names: list[str] = [
        # Velocity / BOCPD
        "drift_velocity_latest",
        "drift_velocity_peak",
        "drift_bits_final",
        "bocpd_changepoint",
        # Risk layers
        "internal_risk",
        "propagated_risk",
        "public_risk",
        "confirmation_lift",
        # Causal signature
        "causal_p_risk",
        "causal_llr",
        "causal_volume_change",
        "causal_margin_change",
        "causal_counterparty_change",
        "causal_corridor_change",
        # Suspicious stability
        "suspicion_score",
        "stability_anomaly",
        "environmental_movement",
        # Dormancy break
        "dormancy_break",
        "dormancy_depth",
        "activation_strength",
    ]

    feature_labels: dict[str, str] = {
        "drift_velocity_latest": "Drift velocity (latest window)",
        "drift_velocity_peak": "Drift velocity peaked at {value:.2f} bits/month",
        "drift_bits_final": "Accumulated drift: {value:.2f} bits",
        "bocpd_changepoint": "BOCPD regime change detected",
        "internal_risk": "Internal risk score {value:.2f}",
        "propagated_risk": "Contagion risk {value:.2f}",
        "public_risk": "Public intelligence risk {value:.2f}",
        "confirmation_lift": "Internal–public confirmation lift {value:.1f}x",
        "causal_p_risk": "Causal risk probability {value:.2f}",
        "causal_llr": "Causal log-likelihood ratio {value:.2f}",
        "causal_volume_change": "Volume change in drift window",
        "causal_margin_change": "Margin compression (laundering signal)",
        "causal_counterparty_change": "Counterparty risk escalation",
        "causal_corridor_change": "Corridor risk shift",
        "suspicion_score": "Suspicious stability score {value:.2f}",
        "stability_anomaly": "Stability anomaly vs cohort {value:.2f}",
        "environmental_movement": "Environmental risk movement {value:.2f}",
        "dormancy_break": "Dormancy-break composite {value:.2f}",
        "dormancy_depth": "Dormancy depth {value:.2f}",
        "activation_strength": "Activation burst strength {value:.2f}",
    }

    def extract(self, case: Any, client_context: dict | None = None) -> dict[str, float]:
        """Extract drift features from an analysis dict.

        Args:
            case: The analysis dict returned by DriftEngine._analyze_customer().
                  The base-class ``Case`` type is not applicable to drift — this
                  extractor is wired directly to the engine's analysis output.
            client_context: Unused; present for base-class compatibility.
        """
        a: dict = case if isinstance(case, dict) else {}

        causal = a.get("causal")
        stability = a.get("stability")
        dormancy = a.get("dormancy")

        sig = getattr(causal, "signature", None) if causal is not None else None

        return {
            "drift_velocity_latest": float(a.get("latest_velocity", 0.0)),
            "drift_velocity_peak": float(a.get("max_velocity", 0.0)),
            "drift_bits_final": float(a.get("final_drift", 0.0)),
            "bocpd_changepoint": 1.0 if a.get("bocpd_changepoint_day") is not None else 0.0,
            "internal_risk": float(a.get("internal_risk", 0.0)),
            "propagated_risk": float(a.get("propagated_risk", 0.0)),
            "public_risk": float(a.get("public_risk", 0.0)),
            "confirmation_lift": float(a.get("confirmation_lift", 1.0)),
            "causal_p_risk": float(getattr(causal, "p_risk", 0.0)),
            "causal_llr": float(getattr(causal, "causal_llr", 0.0)),
            "causal_volume_change": float(getattr(sig, "volume_change", 0.0)),
            "causal_margin_change": float(getattr(sig, "margin_change", 0.0)),
            "causal_counterparty_change": float(getattr(sig, "counterparty_change", 0.0)),
            "causal_corridor_change": float(getattr(sig, "corridor_change", 0.0)),
            "suspicion_score": float(getattr(stability, "suspicion", 0.0)),
            "stability_anomaly": float(getattr(stability, "stability_anomaly", 0.0)),
            "environmental_movement": float(getattr(stability, "environmental_movement", 0.0)),
            "dormancy_break": float(getattr(dormancy, "dormancy_break", 0.0)),
            "dormancy_depth": float(getattr(dormancy, "dormancy_depth", 0.0)),
            "activation_strength": float(getattr(dormancy, "activation_strength", 0.0)),
        }
