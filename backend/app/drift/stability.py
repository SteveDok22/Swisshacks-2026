"""
Suspicious Stability — the slow-walker / sleeper detector.

Every other layer hunts for MOVEMENT (drift, velocity, changepoint). But a
sophisticated launderer who knows the bank watches for drift does the obvious
thing: move even more slowly, keep metrics smooth, never trip a threshold.

The inversion: real customers JITTER. Their metrics wobble naturally. A
customer who holds an unnaturally smooth trajectory — ESPECIALLY while their
environment (counterparties, corridors, public signals) is moving — is an
anomaly in itself. This is not drift. It is anti-drift.

We never flag stability alone. Most of the book is calm, and calm in a calm
environment is just a normal customer. The signal is the COMBINATION:

    suspicion = stability_anomaly  x  environmental_movement

Both factors must be present. A product, not a sum: a perfectly smooth
customer in a quiet world scores ~0; a perfectly smooth customer while the
world around him moves scores high.

Pure numpy. ~120 lines.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class StabilityResult:
    """Suspicious-stability assessment for one customer."""

    suspicion: float            # 0..1 final score (product of the two factors)
    stability_anomaly: float    # 0..1 how unnaturally smooth the customer is
    environmental_movement: float  # 0..1 how much the surroundings move
    own_volatility: float       # raw coefficient of variation of the customer
    cohort_volatility: float    # median CV across the cohort (reference)
    is_suspicious: bool         # suspicion above the flag threshold
    detail: str


def _coefficient_of_variation(monthly: list[np.ndarray]) -> float:
    """
    Coefficient of variation (std/mean) of monthly means — a scale-free
    measure of how much a customer's level wobbles month to month.
    Real businesses have natural CV; a near-zero CV is robotic.
    """
    if not monthly:
        return 0.0
    means = np.array([float(np.mean(m)) for m in monthly if len(m) > 0])
    if len(means) < 2:
        return 0.0
    mu = float(np.mean(means))
    if abs(mu) < 1e-9:
        return 0.0
    return float(np.std(means) / abs(mu))


def cohort_volatility(book_monthly: list[list[np.ndarray]]) -> float:
    """Median coefficient of variation across the whole cohort (the norm)."""
    cvs = [_coefficient_of_variation(m) for m in book_monthly]
    cvs = [c for c in cvs if c > 0]
    if not cvs:
        return 0.05
    return float(np.median(cvs))


def assess_stability(
    customer_monthly: list[np.ndarray],
    cohort_cv: float,
    *,
    counterparty_monthly: list[np.ndarray] | None = None,
    corridor_monthly: list[np.ndarray] | None = None,
    public_risk: float = 0.0,
    flag_threshold: float = 0.35,
) -> StabilityResult:
    """
    Assess suspicious stability for one customer.

    Parameters
    ----------
    customer_monthly:
        The customer's monthly volume arrays (own behavior).
    cohort_cv:
        Median coefficient of variation across the cohort (reference norm).
    counterparty_monthly, corridor_monthly:
        The customer's environment metrics — movement here while the customer
        stays smooth is the suspicious combination.
    public_risk:
        External-signal risk (0..1). Public noise about a customer who stays
        calm is part of "environment moving".
    """
    own_cv = _coefficient_of_variation(customer_monthly)

    # --- Factor 1: stability anomaly ---
    # How much SMOOTHER is the customer than the cohort norm? If own_cv is far
    # below cohort_cv, the customer is unnaturally smooth. Ratio in [0,1]:
    # 1 = perfectly flat vs a lively cohort, 0 = as jittery as everyone else.
    if cohort_cv < 1e-9:
        stability_anomaly = 0.0
    else:
        ratio = own_cv / cohort_cv
        # Anomaly rises as own volatility falls below ~half the cohort norm
        stability_anomaly = float(np.clip(1.0 - ratio / 0.5, 0.0, 1.0))

    # --- Factor 2: environmental movement ---
    # Does the world around the customer move? Counterparty/corridor drift in
    # the customer's own book, plus public signals about them.
    env_components = []
    if counterparty_monthly:
        cp_move = _trend_magnitude(counterparty_monthly)
        env_components.append(min(cp_move / 0.3, 1.0))
    if corridor_monthly:
        co_move = _trend_magnitude(corridor_monthly)
        env_components.append(min(co_move / 0.3, 1.0))
    env_components.append(min(public_risk / 0.5, 1.0))
    environmental_movement = float(np.clip(np.mean(env_components), 0.0, 1.0)) if env_components else 0.0

    # --- Combine: PRODUCT (both must be present) ---
    suspicion = stability_anomaly * environmental_movement

    if suspicion >= flag_threshold:
        detail = (
            f"Unnaturally smooth (CV {own_cv:.3f} vs cohort {cohort_cv:.3f}) "
            f"while environment moves — possible slow-walker"
        )
    elif stability_anomaly > 0.5:
        detail = f"Smooth profile (CV {own_cv:.3f}) but quiet environment — not alarming"
    else:
        detail = f"Normal volatility (CV {own_cv:.3f})"

    return StabilityResult(
        suspicion=suspicion,
        stability_anomaly=stability_anomaly,
        environmental_movement=environmental_movement,
        own_volatility=own_cv,
        cohort_volatility=cohort_cv,
        is_suspicious=suspicion >= flag_threshold,
        detail=detail,
    )


def _trend_magnitude(monthly: list[np.ndarray]) -> float:
    """
    Absolute change in monthly mean from the first third to the last third —
    a simple, robust measure of whether a metric is moving over time.
    """
    if len(monthly) < 3:
        return 0.0
    means = np.array([float(np.mean(m)) for m in monthly if len(m) > 0])
    if len(means) < 3:
        return 0.0
    third = max(len(means) // 3, 1)
    early = float(np.mean(means[:third]))
    late = float(np.mean(means[-third:]))
    return abs(late - early)
