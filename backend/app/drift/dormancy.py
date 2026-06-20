"""
Dormancy-Break — the sleeper-account reactivation detector.

AMINA use case: "Previously dormant company begins high transaction volume"
-> "Dormancy Break - Suspicious Activation".

Every drift layer assumes a customer who is *doing something* the whole time.
A dormant shell is the opposite: near-zero activity for a long stretch, then a
sudden burst. The drift/velocity layers can under-react to this because the
baseline is so quiet that even a large absolute jump looks like "starting from
nothing" rather than a regime change.

So we detect it explicitly, on its own terms:

    1. BASELINE was genuinely dormant  (early months near-zero volume)
    2. ACTIVATION is a real burst       (late months jump far above baseline)

dormancy_break = dormancy_depth  x  activation_strength

A product, not a sum: a company that was dormant but stays dormant scores ~0;
a company that was always active and merely grew scores ~0 (that is ordinary
drift, handled elsewhere). Only the dormant -> active transition scores high.

Pure numpy. No external API.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DormancyResult:
    """Dormancy-break assessment for one customer."""

    dormancy_break: float       # 0..1 final score (product of the two factors)
    dormancy_depth: float       # 0..1 how dormant the baseline period was
    activation_strength: float  # 0..1 how strong the later burst is
    baseline_volume: float      # raw mean volume in the dormant window
    active_volume: float        # raw mean volume in the active window
    is_dormancy_break: bool     # above the flag threshold
    detail: str


def _window_means(monthly: list[np.ndarray]) -> np.ndarray:
    """Per-month mean volume as a 1-D array.

    Empty months are skipped, so the baseline/active split below operates over
    the sequence of *non-empty* months. For the synthetic book every month has
    observations, so this is a no-op there; it only matters for sparse inputs.
    """
    return np.array([float(np.mean(m)) for m in monthly if len(m) > 0])


def assess_dormancy(
    customer_monthly: list[np.ndarray],
    *,
    baseline_fraction: float = 0.5,
    dormant_ceiling: float = 0.15,
    activation_floor: float = 4.0,
    flag_threshold: float = 0.35,
) -> DormancyResult:
    """
    Detect a dormant-to-active reactivation in a customer's volume series.

    Parameters
    ----------
    customer_monthly:
        The customer's monthly volume arrays (own behavior).
    baseline_fraction:
        Portion of the series treated as the "baseline" window (early months).
    dormant_ceiling:
        Baseline mean below this fraction of the overall mean counts as dormant.
    activation_floor:
        Active mean must exceed the baseline mean by at least this multiple to
        count as a genuine burst (guards against dividing a tiny baseline).
    flag_threshold:
        dormancy_break at or above this is flagged.
    """
    means = _window_means(customer_monthly)
    if len(means) < 4:
        return DormancyResult(
            dormancy_break=0.0,
            dormancy_depth=0.0,
            activation_strength=0.0,
            baseline_volume=0.0,
            active_volume=0.0,
            is_dormancy_break=False,
            detail="Insufficient history for dormancy assessment",
        )

    split = max(int(len(means) * baseline_fraction), 1)
    baseline = means[:split]
    active = means[split:]

    baseline_vol = float(np.mean(baseline))
    active_vol = float(np.mean(active))
    overall = float(np.mean(means))

    # --- Factor 1: dormancy depth ---
    # How quiet was the baseline RELATIVE to the customer's own overall level?
    # A baseline far below the overall mean means the early period was dormant.
    if overall < 1e-9:
        dormancy_depth = 0.0
    else:
        rel = baseline_vol / overall
        # depth rises as the baseline falls below `dormant_ceiling` of overall
        dormancy_depth = float(np.clip(1.0 - rel / dormant_ceiling, 0.0, 1.0))

    # --- Factor 2: activation strength ---
    # How big is the later burst versus the dormant baseline? Use a small floor
    # on the baseline so a near-zero baseline does not explode the ratio.
    safe_baseline = max(baseline_vol, overall * 0.01, 1e-9)
    jump_ratio = active_vol / safe_baseline
    # strength saturates once the burst is well above the activation floor
    activation_strength = float(np.clip(
        (jump_ratio - activation_floor) / activation_floor, 0.0, 1.0
    ))

    # --- Combine: PRODUCT (both must be present) ---
    dormancy_break = dormancy_depth * activation_strength

    if dormancy_break >= flag_threshold:
        detail = (
            f"Dormant baseline ({baseline_vol:,.0f}) then {jump_ratio:.1f}x "
            f"surge to {active_vol:,.0f} - suspicious activation"
        )
    elif dormancy_depth > 0.5 and activation_strength <= 0.1:
        detail = f"Quiet baseline ({baseline_vol:,.0f}) but no burst - still dormant"
    else:
        detail = "No dormancy-break pattern"

    return DormancyResult(
        dormancy_break=dormancy_break,
        dormancy_depth=dormancy_depth,
        activation_strength=activation_strength,
        baseline_volume=baseline_vol,
        active_volume=active_vol,
        is_dormancy_break=dormancy_break >= flag_threshold,
        detail=detail,
    )
