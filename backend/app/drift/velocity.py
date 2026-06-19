"""
Drift velocity — the Drift Engine's signature metric.

Let P_0 be the customer's profile distribution estimated at onboarding
(declared + first verified window) and P_t the current rolling estimate.

    Drift(t) = KL( P_0 || P_t )        accumulated divergence, in bits
    DV(t)    = d/dt Drift(t)           drift velocity, bits per month

Low DV = natural life evolution. High DV = structural transformation.
Rising DV (acceleration) is the earliest available precursor signal —
it fires before the absolute divergence crosses any sane alert threshold.

We model each monitored metric (volume, counterparty-risk mix, corridor mix,
tx frequency) as a Gaussian per window and use the closed-form Gaussian KL.
Multi-metric drift is the sum over metrics (independence approximation,
consistent with the layer-orthogonality design).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LOG2 = float(np.log(2.0))


def gaussian_kl_bits(mu0: float, var0: float, mu1: float, var1: float) -> float:
    """KL( N(mu0,var0) || N(mu1,var1) ) in bits. Closed form."""
    var0 = max(var0, 1e-9)
    var1 = max(var1, 1e-9)
    nats = 0.5 * (np.log(var1 / var0) + (var0 + (mu0 - mu1) ** 2) / var1 - 1.0)
    return float(max(nats, 0.0) / LOG2)


@dataclass
class DriftSeries:
    """Per-window drift trajectory for one customer."""

    # Window end indices (e.g. month numbers)
    windows: list[int]
    # Accumulated KL divergence vs baseline, bits
    drift_bits: list[float]
    # Drift velocity: first difference of drift_bits, bits/window
    velocity: list[float]
    # Velocity trend (acceleration): first difference of velocity
    acceleration: list[float]


def compute_drift_series(
    metric_windows: dict[str, list[np.ndarray]],
    baseline_windows: int = 3,
) -> DriftSeries:
    """
    Compute the drift trajectory for one customer.

    Parameters
    ----------
    metric_windows:
        metric name -> list of per-window observation arrays
        (e.g. "monthly_volume" -> [month1 array, month2 array, ...]).
        All metrics must have the same number of windows.
    baseline_windows:
        Number of initial windows pooled into the P_0 baseline. These
        represent the verified onboarding period.

    Returns
    -------
    DriftSeries with drift, velocity, and acceleration per window.
    """
    metrics = list(metric_windows.keys())
    if not metrics:
        return DriftSeries(windows=[], drift_bits=[], velocity=[], acceleration=[])

    n_windows = len(metric_windows[metrics[0]])
    if any(len(metric_windows[m]) != n_windows for m in metrics):
        raise ValueError("all metrics must have the same number of windows")
    if n_windows <= baseline_windows:
        return DriftSeries(windows=[], drift_bits=[], velocity=[], acceleration=[])

    # Baseline P_0 per metric: pooled over the first `baseline_windows`
    baseline_params: dict[str, tuple[float, float]] = {}
    for m in metrics:
        pooled = np.concatenate(metric_windows[m][:baseline_windows])
        baseline_params[m] = (float(np.mean(pooled)), float(np.var(pooled)))

    windows: list[int] = []
    drift_bits: list[float] = []

    for w in range(baseline_windows, n_windows):
        total = 0.0
        for m in metrics:
            obs = metric_windows[m][w]
            if len(obs) == 0:
                continue
            mu0, var0 = baseline_params[m]
            mu_t = float(np.mean(obs))
            # Robustness choice: evaluate the KL using the BASELINE variance
            # on both sides. Window-level variance estimates over ~21 daily
            # observations are extremely noisy and dominate the KL, drowning
            # the mean-shift signal we actually care about. Mean-shift KL
            # with shared variance reduces to (mu_t - mu0)^2 / (2 var0) nats,
            # a clean squared-z-score — exactly the structural-change signal.
            total += gaussian_kl_bits(mu0, var0, mu_t, var0)
        windows.append(w)
        drift_bits.append(total)

    # Smooth the drift trajectory (rolling mean, window 3) before
    # differentiating — differentiation amplifies noise.
    smoothed: list[float] = []
    for i in range(len(drift_bits)):
        lo = max(0, i - 2)
        smoothed.append(float(np.mean(drift_bits[lo : i + 1])))

    velocity = [0.0] + [
        smoothed[i] - smoothed[i - 1] for i in range(1, len(smoothed))
    ]
    acceleration = [0.0] + [
        velocity[i] - velocity[i - 1] for i in range(1, len(velocity))
    ]

    return DriftSeries(
        windows=windows,
        drift_bits=smoothed,
        velocity=velocity,
        acceleration=acceleration,
    )


def velocity_band(dv: float) -> str:
    """
    Map drift velocity (bits/window) to an interpretation band.

    Thresholds calibrated on the synthetic validation suite (generate_book):
    stable customers peak at ~0.65 bits/window of noise velocity; genuine
    drift scenarios start at ~1.0 and reach 12+. The 0.8 boundary sits in
    the empirical gap between the two populations.
    """
    if dv < 0.30:
        return "natural"
    if dv < 0.80:
        return "notable"
    if dv < 3.00:
        return "structural"
    return "rapid"
