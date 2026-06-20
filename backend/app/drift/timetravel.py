"""
Time-Travel Audit — as-of replay with no look-ahead.

The regulator's question: "How do you prove this escalation wasn't fitted
after the fact? Maybe you knew the customer would go bad and drew the chart
to make the system look clever."

This is the look-ahead bias question, and it is the difference between a
forecasting system a bank can defend to FINMA and a pretty animation.

Our honest position: the underlying engine is causal by construction.
- BOCPD is an ONLINE algorithm — it processes the stream left to right and
  physically cannot use data that has not arrived yet.
- Drift velocity is a trailing-window derivative.

So we can do an honest as-of replay: freeze time at month T and recompute the
score using ONLY data up to and including T. If, at month T = sanctions - 7,
the system would already have raised a high score, that is proof it would have
led the event WITHOUT knowing the future.

The real work here is not drawing a chart. It is rigorously TRUNCATING every
source of future information:
  - transaction metrics: only months 0..T
  - public signals: only those dated <= T (a Reuters story from month 14
    does not exist at month 7)
  - contagion: the sanctions listing happens at month `sanctions_month`; before
    that month the seed entity is NOT yet flagged, so propagated risk is 0
  - causal signature: baseline vs a recent window that ENDS at T, never later

This module reuses the live engine's core internal/public weighting parameters,
applied to truncated inputs. Replay-specific causal scoring remains free of
future data and does not apply full-book anomaly floors.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import (
    DRIFT_INTERNAL_ACCUMULATED_WEIGHT,
    DRIFT_INTERNAL_CONTAGION_WEIGHT,
    DRIFT_INTERNAL_VELOCITY_WEIGHT,
    DRIFT_PUBLIC_RISK_WEIGHT,
)
from app.drift.causal import classify_causal, compute_signature
from app.drift.public_intel import assess_public_risk, generate_signals_for_customer
from app.drift.simulator import SyntheticCustomer
from app.drift.velocity import compute_drift_series


@dataclass
class AsOfPoint:
    """The score the system WOULD have produced at a given month, using only
    data available up to that month."""

    month: int
    as_of_score: float
    velocity: float
    public_risk: float        # only signals dated <= month
    contagion_active: bool    # whether the sanctions listing had happened yet
    causal_p_risk: float


def _truncate_windows(
    metric_windows: dict[str, list[np.ndarray]], upto_month: int
) -> dict[str, list[np.ndarray]]:
    """Keep only months 0..upto_month (inclusive) for every metric."""
    return {
        metric: arrs[: upto_month + 1] for metric, arrs in metric_windows.items()
    }


def replay_as_of(
    cust: SyntheticCustomer,
    month_t: int,
    *,
    propagated_risk_final: float,
    contagion_listing_month: int | None,
) -> AsOfPoint:
    """
    Recompute the customer's drift score AS OF month_t, using only information
    available at that time. No data after month_t may influence the result.

    Parameters
    ----------
    propagated_risk_final:
        The customer's propagated contagion risk in the present (final) state.
        It only becomes active once the sanctions listing has occurred, i.e.
        for month_t >= contagion_listing_month.
    contagion_listing_month:
        The month the seed entity was sanctioned. Before this, contagion = 0.
    """
    # --- Truncate behavioral metrics to [0, T] ---
    full_windows = cust.metric_windows()  # behavioral (no margin)
    trunc = _truncate_windows(full_windows, month_t)

    # Velocity as-of T (trailing — already causal, but we feed truncated data)
    ds = compute_drift_series(trunc)
    max_vel = max(ds.velocity) if ds.velocity else 0.0
    final_drift = ds.drift_bits[-1] if ds.drift_bits else 0.0

    # --- Public signals: only those dated <= T ---
    all_signals = generate_signals_for_customer(
        cust.customer_id, cust.name, cust.scenario, months=cust.months,
        drift_start_month=cust.drift_start_month,
        seed=hash(cust.customer_id) % 9999,
    )
    past_signals = [s for s in all_signals if s.month <= month_t]
    pi = assess_public_risk(past_signals, months=cust.months)

    # --- Contagion: only active once the listing has happened ---
    contagion_active = (
        contagion_listing_month is not None and month_t >= contagion_listing_month
    )
    prop_risk = propagated_risk_final if contagion_active else 0.0

    # --- Internal risk (same formula as live engine) ---
    vel_norm = min(max_vel / 3.0, 1.0)
    drift_norm = min(final_drift / 20.0, 1.0)
    internal_risk = min(
        DRIFT_INTERNAL_VELOCITY_WEIGHT * vel_norm
        + DRIFT_INTERNAL_ACCUMULATED_WEIGHT * drift_norm
        + DRIFT_INTERNAL_CONTAGION_WEIGHT * prop_risk,
        1.0,
    )

    # --- Causal as-of: signature from baseline vs window ending at T ---
    causal_trunc = _truncate_windows(cust.causal_windows(), month_t)
    sig = compute_signature(causal_trunc)
    causal = classify_causal(sig)

    # --- Fused score (same shape as live engine) ---
    base = max(internal_risk, pi.public_risk * DRIFT_PUBLIC_RISK_WEIGHT)
    score = min(base * 100.0, 100.0)
    causal_factor = 0.45 + 0.55 * causal.p_risk
    score = min(score * causal_factor, 100.0)

    return AsOfPoint(
        month=month_t,
        as_of_score=round(score, 1),
        velocity=round(max_vel, 3),
        public_risk=round(pi.public_risk, 3),
        contagion_active=contagion_active,
        causal_p_risk=round(causal.p_risk, 3),
    )


def replay_trajectory(
    cust: SyntheticCustomer,
    *,
    propagated_risk_final: float,
    contagion_listing_month: int | None,
    alert_threshold: float = 40.0,
) -> dict:
    """
    Full as-of replay across all months. Returns the trajectory plus the
    earliest month the system would have crossed the alert threshold and the
    resulting lead time before the sanctions listing.
    """
    points = [
        replay_as_of(
            cust, t,
            propagated_risk_final=propagated_risk_final,
            contagion_listing_month=contagion_listing_month,
        )
        for t in range(cust.months)
    ]

    # First month the as-of score crosses the alert threshold
    alert_month = next(
        (p.month for p in points if p.as_of_score >= alert_threshold), None
    )

    lead_time = None
    if alert_month is not None and cust.sanctions_month is not None:
        lead_time = cust.sanctions_month - alert_month

    return {
        "points": points,
        "alert_month": alert_month,
        "sanctions_month": cust.sanctions_month,
        "lead_time_months": lead_time,
        "alert_threshold": alert_threshold,
    }
