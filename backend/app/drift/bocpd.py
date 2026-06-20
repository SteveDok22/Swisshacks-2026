"""
Bayesian Online Changepoint Detection (BOCPD).

Implementation of Adams & MacKay (2007), arXiv:0710.3742, with a
Normal-Inverse-Gamma conjugate predictive (Student-t posterior predictive).

Core idea: maintain a posterior over the "run length" r_t — the number of
observations since the last changepoint. A spike in P(r_t = 0) means the
generative process behind the data stream has just changed.

Why this matters for KYC drift: threshold rules catch OUTLIERS; BOCPD catches
REGIME CHANGE. A customer who slowly raised average monthly volume from 5K to
9K never crosses a 10K threshold, but the distribution shift is plainly
visible to the run-length posterior.

Pure numpy. No exotic dependencies. ~150 lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class BOCPDResult:
    """Output of a BOCPD pass over a series."""

    # P(changepoint at step t) = run-length-0 posterior, length T
    changepoint_probs: np.ndarray
    # Most likely run length at each step, length T
    map_run_lengths: np.ndarray
    # Indices where changepoint probability exceeded the detection threshold
    detected_changepoints: list[int] = field(default_factory=list)


class BOCPD:
    """
    Online changepoint detector with Normal-Inverse-Gamma conjugate model.

    Parameters
    ----------
    hazard:
        Constant hazard rate H = 1/expected_run_length. We default to 1/250 —
        roughly one regime change per business year of daily observations.
    mu0, kappa0, alpha0, beta0:
        NIG prior hyperparameters. Defaults are weakly informative; callers
        should standardize their series (z-score) before feeding it in, which
        makes these defaults appropriate for any metric.
    detection_threshold:
        P(r_t = 0) above which we record a detected changepoint.
    """

    def __init__(
        self,
        hazard: float = 1.0 / 250.0,
        mu0: float = 0.0,
        kappa0: float = 1.0,
        alpha0: float = 1.0,
        beta0: float = 1.0,
        detection_threshold: float = 0.5,
        burn_in: int = 10,
        min_drop: int = 8,
    ) -> None:
        self.hazard = hazard
        self.mu0 = mu0
        self.kappa0 = kappa0
        self.alpha0 = alpha0
        self.beta0 = beta0
        self.detection_threshold = detection_threshold
        self.burn_in = burn_in
        self.min_drop = min_drop

    def run(self, series: np.ndarray) -> BOCPDResult:
        """
        Run BOCPD over a 1-D series. Returns per-step changepoint probabilities
        and MAP run lengths.

        The series should be roughly standardized (the simulator and the
        drift service z-score their inputs against the baseline window).
        """
        x = np.asarray(series, dtype=float)
        T = len(x)
        if T == 0:
            return BOCPDResult(
                changepoint_probs=np.zeros(0),
                map_run_lengths=np.zeros(0, dtype=int),
            )

        # Run-length posterior. R[r, t] = P(r_t = r | x_1:t).
        # We only ever need the current column; keep full matrix for clarity
        # (T is small in our use — months of daily data).
        R = np.zeros((T + 1, T + 1))
        R[0, 0] = 1.0

        # Sufficient statistics per possible run length (vectors grow with t)
        mu = np.array([self.mu0])
        kappa = np.array([self.kappa0])
        alpha = np.array([self.alpha0])
        beta = np.array([self.beta0])

        changepoint_probs = np.zeros(T)
        map_run_lengths = np.zeros(T, dtype=int)
        detected: list[int] = []

        for t in range(T):
            xt = x[t]

            # Posterior predictive of x_t under each run-length hypothesis:
            # Student-t with df=2*alpha, loc=mu, scale=sqrt(beta*(kappa+1)/(alpha*kappa))
            scale = np.sqrt(beta * (kappa + 1.0) / (alpha * kappa))
            pred = stats.t.pdf(xt, df=2.0 * alpha, loc=mu, scale=scale)
            pred = np.maximum(pred, 1e-12)  # numerical floor

            # Growth probabilities: run continues
            growth = R[: t + 1, t] * pred * (1.0 - self.hazard)
            # Changepoint probability: any run resets to 0
            cp = np.sum(R[: t + 1, t] * pred * self.hazard)

            R[1 : t + 2, t + 1] = growth
            R[0, t + 1] = cp

            # Normalize
            total = R[: t + 2, t + 1].sum()
            if total > 0:
                R[: t + 2, t + 1] /= total

            changepoint_probs[t] = R[0, t + 1]
            map_run_lengths[t] = int(np.argmax(R[: t + 2, t + 1]))

            # Detection rule: a changepoint manifests as a sharp DROP in the
            # MAP run length (posterior mass jumps to short runs), not as
            # P(r=0) crossing a threshold — the mass spreads over r=0..k.
            # We flag when MAP run length falls by more than half AND by at
            # least min_drop steps, after a burn-in period.
            if t >= self.burn_in and t > 0:
                prev_rl = map_run_lengths[t - 1]
                curr_rl = map_run_lengths[t]
                if prev_rl >= self.min_drop and curr_rl < prev_rl // 2:
                    # The run reset happened (curr_rl) steps ago
                    cp_index = t - curr_rl
                    if not detected or cp_index - detected[-1] > self.min_drop:
                        detected.append(cp_index)

            # Update sufficient statistics:
            # new run (r=0) gets the prior; continuing runs absorb x_t
            mu_new = np.empty(t + 2)
            kappa_new = np.empty(t + 2)
            alpha_new = np.empty(t + 2)
            beta_new = np.empty(t + 2)

            mu_new[0] = self.mu0
            kappa_new[0] = self.kappa0
            alpha_new[0] = self.alpha0
            beta_new[0] = self.beta0

            mu_new[1:] = (kappa * mu + xt) / (kappa + 1.0)
            kappa_new[1:] = kappa + 1.0
            alpha_new[1:] = alpha + 0.5
            beta_new[1:] = beta + (kappa * (xt - mu) ** 2) / (2.0 * (kappa + 1.0))

            mu, kappa, alpha, beta = mu_new, kappa_new, alpha_new, beta_new

        return BOCPDResult(
            changepoint_probs=changepoint_probs,
            map_run_lengths=map_run_lengths,
            detected_changepoints=self._confirmed_changepoints(x, detected),
        )

    @staticmethod
    def _confirmed_changepoints(
        series: np.ndarray,
        candidates: list[int],
        confirmation_window: int = 5,
        min_effect_size: float = 1.5,
    ) -> list[int]:
        """Reject isolated outliers by requiring a short sustained level shift.

        Confirmation adds a five-observation detection delay while preserving
        causal behavior: only observations immediately following the candidate
        are used, never the remainder of the series.
        """
        confirmed: list[int] = []
        for cp in candidates:
            before = series[max(0, cp - 20):cp]
            after = series[cp:cp + confirmation_window]
            if len(before) < confirmation_window or len(after) < confirmation_window:
                continue
            pooled_scale = max(float(np.std(np.concatenate([before, after]))), 1e-6)
            effect_size = abs(float(np.mean(after) - np.mean(before))) / pooled_scale
            if effect_size >= min_effect_size:
                confirmed.append(int(cp))
        return confirmed


def standardize(series: np.ndarray, baseline_window: int = 30) -> np.ndarray:
    """
    Z-score a series against its initial baseline window.

    BOCPD priors assume roughly unit-scale data; standardizing against the
    FIRST window (the customer's verified onboarding period) — not the whole
    series — preserves later drift as visible deviation.
    """
    x = np.asarray(series, dtype=float)
    if len(x) == 0:
        return x
    w = x[: max(2, min(baseline_window, len(x)))]
    mu = float(np.mean(w))
    sigma = float(np.std(w))
    if sigma < 1e-9:
        sigma = 1.0
    return (x - mu) / sigma
