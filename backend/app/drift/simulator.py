"""
Synthetic customer simulator — generates transaction streams with known
ground-truth drift scenarios.

This serves three purposes:
1. Demo data (the timeline scrubber replays these histories)
2. Hypothesis validation (H1, H2 from README, Drift Engine section — we know
   exactly when drift was injected, so we can measure detection lead time)
3. The red-team button (POST /drift/inject creates a scenario live)

Scenarios:
- stable:                no drift; the false-positive control group
- volume_creep:          mean transaction volume rises gradually (1%/day)
- counterparty_migration: share of high-risk counterparties grows
- corridor_shift:        payment corridors move toward high-risk countries
- combined:              all three, slowly — the realistic "quiet drift"

Every scenario ends with a simulated sanctions listing at the final month
(month 0 in demo language), so lead time = listing date - detection date.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SCENARIOS = (
    "stable",
    "volume_creep",
    "counterparty_migration",
    "corridor_shift",
    "combined",
    "benign_expansion",
)

# Country risk weights reused conceptually from the social-engineering extractor
CORRIDOR_RISK = {"CH": 0.05, "DE": 0.1, "IT": 0.15, "SG": 0.35, "HK": 0.4, "AE": 0.5, "RU": 0.95, "IR": 1.0}
LOW_RISK = ["CH", "DE", "IT"]
HIGH_RISK = ["RU", "IR", "AE"]


@dataclass
class SyntheticCustomer:
    customer_id: str
    name: str
    scenario: str
    months: int
    # Per-month arrays of daily observations
    monthly_volume: list[np.ndarray] = field(default_factory=list)
    counterparty_risk: list[np.ndarray] = field(default_factory=list)
    corridor_risk: list[np.ndarray] = field(default_factory=list)
    # margin_ratio: profitability proxy = (inflow - outflow) / inflow per day.
    # The CAUSAL discriminator. Benign business growth preserves margin (money
    # comes in and stays / is reinvested); transit laundering collapses margin
    # (money flows straight through — high volume, near-zero retention).
    margin_ratio: list[np.ndarray] = field(default_factory=list)
    # Ground truth: month index where drift injection began (None for stable)
    drift_start_month: int | None = None
    # The simulated sanctions listing always lands on the last month
    sanctions_month: int | None = None
    # Ground-truth causal label for validation: "benign" | "risk" | None
    causal_truth: str | None = None

    def metric_windows(self) -> dict[str, list[np.ndarray]]:
        """Behavioral metrics for velocity/BOCPD (magnitude of drift)."""
        return {
            "monthly_volume": self.monthly_volume,
            "counterparty_risk": self.counterparty_risk,
            "corridor_risk": self.corridor_risk,
        }

    def causal_windows(self) -> dict[str, list[np.ndarray]]:
        """All metrics including margin — for causal signature (direction of
        drift). Margin is the causal discriminator and is kept OUT of the
        velocity computation so the two measures stay orthogonal: velocity
        asks 'how much changed', causal asks 'in which direction'."""
        return {
            "monthly_volume": self.monthly_volume,
            "counterparty_risk": self.counterparty_risk,
            "corridor_risk": self.corridor_risk,
            "margin_ratio": self.margin_ratio,
        }

    def daily_volume_series(self) -> np.ndarray:
        """Concatenated daily volumes across all months (for BOCPD)."""
        if not self.monthly_volume:
            return np.zeros(0)
        return np.concatenate(self.monthly_volume)


def generate_customer(
    customer_id: str,
    name: str,
    scenario: str,
    months: int = 18,
    days_per_month: int = 21,
    base_volume: float = 5_000.0,
    drift_start_month: int = 8,
    seed: int | None = None,
) -> SyntheticCustomer:
    """
    Generate one synthetic customer.

    For drift scenarios, injection begins at `drift_start_month` and ramps
    linearly until the final month — the "slow structural change" AMINA
    describes. The simulated sanctions listing lands on the final month.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {SCENARIOS}")

    rng = np.random.default_rng(seed)
    # Causal ground-truth label: benign_expansion is the only benign drift;
    # all other non-stable scenarios are risk.
    if scenario == "stable":
        causal_truth = None
    elif scenario == "benign_expansion":
        causal_truth = "benign"
    else:
        causal_truth = "risk"

    cust = SyntheticCustomer(
        customer_id=customer_id,
        name=name,
        scenario=scenario,
        months=months,
        drift_start_month=None if scenario == "stable" else drift_start_month,
        sanctions_month=None if scenario in ("stable", "benign_expansion") else months - 1,
        causal_truth=causal_truth,
    )

    for month in range(months):
        # Drift intensity in [0, 1]: 0 before injection, ramps to 1 at the end
        if scenario == "stable" or month < drift_start_month:
            intensity = 0.0
        else:
            span = max(months - 1 - drift_start_month, 1)
            intensity = (month - drift_start_month) / span

        # --- Volume ---
        # Both volume_creep (risk) AND benign_expansion move volume up by the
        # SAME magnitude — so velocity alone cannot tell them apart. The causal
        # layer must distinguish them by OTHER metrics (margin, counterparties).
        vol_mult = 1.0
        if scenario in ("volume_creep", "combined", "benign_expansion"):
            vol_mult = 1.0 + 1.2 * intensity  # up to +120% by the end
        volumes = rng.normal(base_volume * vol_mult, base_volume * 0.15, days_per_month)
        volumes = np.maximum(volumes, 100.0)

        # --- Counterparty risk (share of tx with risky counterparties) ---
        base_risky_share = 0.05
        risky_share = base_risky_share
        if scenario in ("counterparty_migration", "combined"):
            risky_share = base_risky_share + 0.45 * intensity  # up to 50%
        # Benign expansion DIVERSIFIES (slightly more counterparties) but they
        # stay low-risk — share barely moves.
        cp_risk = rng.binomial(1, min(risky_share, 0.95), days_per_month).astype(float)
        cp_risk = cp_risk * rng.uniform(0.6, 1.0, days_per_month) + (1 - cp_risk) * rng.uniform(0.0, 0.15, days_per_month)

        # --- Corridor risk ---
        if scenario in ("corridor_shift", "combined"):
            p_high = 0.03 + 0.5 * intensity
        else:
            p_high = 0.03
        corridors = [
            rng.choice(HIGH_RISK) if rng.random() < p_high else rng.choice(LOW_RISK)
            for _ in range(days_per_month)
        ]
        corridor_risk = np.array([CORRIDOR_RISK[c] for c in corridors])

        # --- Margin ratio (THE causal discriminator) ---
        # Baseline healthy business retains ~25% margin with natural noise.
        # Benign expansion PRESERVES margin (inflow and outflow grow together,
        # profit is reinvested). Transit/laundering scenarios COLLAPSE margin:
        # money flows straight through, retention approaches zero.
        base_margin = 0.25
        if scenario in ("volume_creep", "counterparty_migration", "corridor_shift", "combined"):
            # Risk: margin collapses toward 0 as intensity rises
            margin_mean = base_margin * (1.0 - 0.9 * intensity)
        elif scenario == "benign_expansion":
            # Benign: margin holds (tiny dip from growth costs, then recovers)
            margin_mean = base_margin * (1.0 - 0.1 * intensity)
        else:
            margin_mean = base_margin
        margin = rng.normal(margin_mean, 0.05, days_per_month)
        margin = np.clip(margin, -0.2, 0.6)

        cust.monthly_volume.append(volumes)
        cust.counterparty_risk.append(cp_risk)
        cust.corridor_risk.append(corridor_risk)
        cust.margin_ratio.append(margin)

    return cust


def generate_book(
    n_stable: int = 6,
    seed: int = 42,
) -> list[SyntheticCustomer]:
    """
    Generate the demo book: one customer per drift scenario plus a control
    group of stable customers. Deterministic via seed.
    """
    names_drift = {
        "volume_creep": "Viktor Antonov",
        "counterparty_migration": "Helena Krause",
        "corridor_shift": "Tomas Lindqvist",
        "combined": "Sergei Mikhailov",
        "benign_expansion": "Maria Steiner",
    }
    stable_names = [
        "Anna Keller", "Luca Moretti", "Sophie Brunner",
        "David Meier", "Nina Forster", "Jan Vogel",
    ]

    book: list[SyntheticCustomer] = []
    idx = 1
    for scenario, name in names_drift.items():
        book.append(
            generate_customer(
                customer_id=f"drift-{idx:03d}",
                name=name,
                scenario=scenario,
                seed=seed + idx,
            )
        )
        idx += 1
    for i in range(n_stable):
        book.append(
            generate_customer(
                customer_id=f"drift-{idx:03d}",
                name=stable_names[i % len(stable_names)],
                scenario="stable",
                seed=seed + idx,
            )
        )
        idx += 1
    return book
