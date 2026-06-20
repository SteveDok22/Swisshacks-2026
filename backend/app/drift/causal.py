"""
Causal Drift — distinguishing risky change from normal life.

The problem with pure drift detection: it fires on ANY structural change.
But a customer who sells a business and buys three new ones moves the same
metrics as a customer who becomes a money-laundering conduit. Velocity alone
cannot tell them apart — both show high drift.

The insight: benign and risky change have different CORRELATION SIGNATURES,
not different magnitudes.

    Benign expansion (legal business growth):
        volume UP, margin PRESERVED, counterparties diversify but stay clean,
        corridors stable.

    Risk transit (laundering / being used as a conduit):
        volume UP, margin COLLAPSES (money flows straight through),
        counterparties concentrate on new/risky, corridors shift high-risk.

We model each as a generative hypothesis over the drift signature and compute
a likelihood ratio:

    causal_LLR = log P(observed_signature | RISK) / P(observed_signature | BENIGN)

A positive LLR means the change looks like risk; negative means it looks like
normal life. This turns "how much did it change?" into "does the change have
a risk signature, or a life signature?" — the question an AMINA analyst
actually asks.

Pure numpy. The two hypotheses are expert-specified generative profiles
(defensible priors); in production they would be fit on the bank's own
confirmed-risk vs confirmed-benign cases (closing the human-in-the-loop loop).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

LOG2 = float(np.log(2.0))

# === Scale-jump corroboration (UC6: large funding round / expansion) ===
# A volume jump alone is ambiguous: legal expansion and a laundering conduit
# both move volume up. But when the active period runs at >= 5x the onboarding
# baseline AND a public funding_event corroborates the jump in the same window,
# the expansion is real and large enough to be a *scale risk* in its own right
# (the FTX pattern: a $900M raise whose transaction volumes never matched the
# claimed revenue). We treat that corroboration as positive evidence and add a
# fixed boost to the causal LLR so the customer surfaces for review.
_SCALE_JUMP_THRESHOLD = 5.0       # active_volume / baseline_volume to qualify
_SCALE_JUMP_CORROBORATION_LLR = 1.5  # nats added when corroborated by funding


@dataclass
class CausalSignature:
    """The drift signature: how each metric moved from baseline to current."""

    volume_change: float       # relative change in mean volume (+0.8 = +80%)
    margin_change: float       # absolute change in margin ratio (-0.2 = lost 20pp)
    counterparty_change: float # absolute change in mean counterparty risk
    corridor_change: float     # absolute change in mean corridor risk
    scale_jump_ratio: float = 1.0  # active_volume / baseline_volume (1.0 = flat)


@dataclass
class CausalVerdict:
    """Output of the causal hypothesis competition."""

    causal_llr: float          # log P(O|risk) / P(O|benign), in nats
    p_risk: float              # posterior P(risk | signature), 0..1
    label: str                 # "risk" | "benign" | "ambiguous"
    signature: CausalSignature
    # Per-metric evidence contribution (which metric drove the verdict)
    contributions: dict[str, float]


# === Generative hypothesis profiles ===
# Each profile specifies, for each signature dimension, the expected mean and
# spread GIVEN that drift is happening under that hypothesis. These encode
# domain knowledge: what does a metric look like under benign vs risk drift?
#
# Format: metric -> (mean, std)

_RISK_PROFILE = {
    # Risk transit: volume rises, margin collapses, counterparties get risky,
    # corridors shift high.
    "volume_change": (0.8, 0.5),       # big volume increase expected
    "margin_change": (-0.18, 0.05),    # margin collapses — TIGHT std: this is
                                       # the strongest causal discriminator, so
                                       # we model it with high confidence
    "counterparty_change": (0.25, 0.18),  # counterparty risk rises (wide: may
                                          # or may not be the active signal)
    "corridor_change": (0.15, 0.15),   # corridors shift high-risk (wide)
}

_BENIGN_PROFILE = {
    # Benign expansion: volume rises (same!), but margin holds, counterparties
    # stay clean, corridors stable.
    "volume_change": (0.8, 0.5),       # SAME volume increase — not discriminative
    "margin_change": (-0.02, 0.04),    # margin roughly preserved — TIGHT
    "counterparty_change": (0.02, 0.10),  # counterparties stay clean
    "corridor_change": (0.0, 0.10),    # corridors stable
}


def _gaussian_log_density(x: float, mean: float, std: float) -> float:
    std = max(std, 1e-6)
    z = (x - mean) / std
    return -0.5 * z * z - np.log(std) - 0.5 * np.log(2 * np.pi)


def _recent_window_start(n: int, baseline_windows: int) -> int:
    """First index of the recent ("active") window over ``n`` monthly windows.

    Single source of truth for the baseline-vs-recent split so the scale-jump
    funding alignment in ``causal_assessment`` cannot drift from the window
    ``compute_signature`` actually reads from.
    """
    return max(baseline_windows, n - 3)


def compute_signature(metric_windows: dict[str, list[np.ndarray]], baseline_windows: int = 3) -> CausalSignature:
    """
    Compute the drift signature: how each metric moved from the onboarding
    baseline to the recent period.
    """
    def window_mean(arrs: list[np.ndarray], lo: int, hi: int) -> float:
        chunk = arrs[lo:hi]
        if not chunk:
            return 0.0
        return float(np.mean(np.concatenate(chunk)))

    n = len(metric_windows.get("monthly_volume", []))
    if n <= baseline_windows:
        return CausalSignature(0.0, 0.0, 0.0, 0.0)

    recent_lo = _recent_window_start(n, baseline_windows)

    vol_base = window_mean(metric_windows["monthly_volume"], 0, baseline_windows)
    vol_recent = window_mean(metric_windows["monthly_volume"], recent_lo, n)
    safe_base = max(vol_base, 1e-6)
    volume_change = (vol_recent - vol_base) / safe_base
    # Scale-jump ratio: how many times larger the active period runs vs baseline
    # (UC6). Distinct from volume_change (a relative delta) so the >= 5x scale
    # test reads directly off the signature.
    scale_jump_ratio = vol_recent / safe_base

    def abs_change(metric: str) -> float:
        if metric not in metric_windows:
            return 0.0
        base = window_mean(metric_windows[metric], 0, baseline_windows)
        recent = window_mean(metric_windows[metric], recent_lo, n)
        return recent - base

    return CausalSignature(
        volume_change=volume_change,
        margin_change=abs_change("margin_ratio"),
        counterparty_change=abs_change("counterparty_risk"),
        corridor_change=abs_change("corridor_risk"),
        scale_jump_ratio=scale_jump_ratio,
    )


def classify_causal(
    signature: CausalSignature,
    *,
    prior_risk: float = 0.5,
    ambiguous_band: float = 1.0,
    funding_corroborated: bool = False,
) -> CausalVerdict:
    """
    Compete the two hypotheses. Returns the causal LLR and posterior.

    causal_llr > 0  -> looks like risk
    causal_llr < 0  -> looks like benign life
    |causal_llr| < ambiguous_band -> not enough signal to call

    Per-metric contributions show WHICH dimension drove the verdict — the
    explainability the analyst needs.

    ``funding_corroborated`` (UC6) signals that a public ``funding_event`` was
    observed in the same window as the drift. Combined with a scale-jump ratio
    >= ``_SCALE_JUMP_THRESHOLD`` it adds a fixed positive boost to the LLR: a
    large, funding-confirmed expansion is a scale risk in its own right and must
    surface for review. The boost is recorded as a ``scale_jump_funding``
    contribution for explainability.
    """
    sig_dict = {
        "volume_change": signature.volume_change,
        "margin_change": signature.margin_change,
        "counterparty_change": signature.counterparty_change,
        "corridor_change": signature.corridor_change,
    }

    contributions: dict[str, float] = {}
    total_llr = 0.0
    for metric, value in sig_dict.items():
        rmean, rstd = _RISK_PROFILE[metric]
        bmean, bstd = _BENIGN_PROFILE[metric]
        ll_risk = _gaussian_log_density(value, rmean, rstd)
        ll_benign = _gaussian_log_density(value, bmean, bstd)
        metric_llr = ll_risk - ll_benign

        # Asymmetric handling — the forensic principle that "absence of evidence
        # is not evidence of absence". A metric sitting in its NEUTRAL zone
        # (neither clearly risk nor clearly benign) should not actively argue
        # AGAINST risk just because the risk profile expected movement there.
        # Risk often shows in one or two metrics, not all at once: a margin
        # collapse alone is a strong transit signal even if counterparties stay
        # clean. So we floor each metric's negative (pro-benign) contribution
        # unless the value is genuinely in the benign region.
        #
        # A value is "genuinely benign" for a metric if it is close to the
        # benign mean (within 1 std). Only then may it contribute negative LLR.
        if metric_llr < 0:
            z_benign = abs(value - bmean) / max(bstd, 1e-6)
            if z_benign > 1.0:
                # Value is not actually near the benign expectation either —
                # it is in a neutral/ambiguous zone. Damp the anti-risk pull.
                metric_llr *= 0.25

        contributions[metric] = metric_llr
        total_llr += metric_llr

    # Scale-jump corroboration (UC6): a >= 5x active/baseline volume jump that a
    # public funding_event confirms in the same window is positive risk evidence.
    if funding_corroborated and signature.scale_jump_ratio >= _SCALE_JUMP_THRESHOLD:
        contributions["scale_jump_funding"] = _SCALE_JUMP_CORROBORATION_LLR
        total_llr += _SCALE_JUMP_CORROBORATION_LLR

    # Posterior via logistic of (LLR + log prior odds)
    log_prior_odds = np.log(prior_risk / max(1 - prior_risk, 1e-6))
    p_risk = 1.0 / (1.0 + np.exp(-(total_llr + log_prior_odds)))

    if total_llr > ambiguous_band:
        label = "risk"
    elif total_llr < -ambiguous_band:
        label = "benign"
    else:
        label = "ambiguous"

    return CausalVerdict(
        causal_llr=float(total_llr),
        p_risk=float(p_risk),
        label=label,
        signature=signature,
        contributions={k: float(v) for k, v in contributions.items()},
    )


def causal_assessment(
    metric_windows: dict[str, list[np.ndarray]],
    *,
    funding_event_months: Sequence[int] | None = None,
    baseline_windows: int = 3,
) -> CausalVerdict:
    """Convenience: signature + classification in one call.

    ``funding_event_months`` (UC6) are the months at which public
    ``funding_event`` signals were observed. A funding event lands "in the same
    window" as the scale jump when it falls inside the recent window that
    ``compute_signature`` reads from — keeping the windowing logic in one place.
    """
    sig = compute_signature(metric_windows, baseline_windows=baseline_windows)

    n = len(metric_windows.get("monthly_volume", []))
    recent_lo = _recent_window_start(n, baseline_windows)
    funding_corroborated = any(
        recent_lo <= month < n for month in (funding_event_months or ())
    )

    return classify_causal(sig, funding_corroborated=funding_corroborated)
