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
- dormancy_break:        near-zero baseline then a sudden volume burst (the
                         reactivated sleeper / "suspicious activation")
- news_spike:            reputational risk (UC 1) — a sustained negative-news
                         event spike whose external story confirms an internal
                         volume drift + margin collapse (the Wirecard pattern)
- pivot:                 a public business-model pivot (UC 10, Centra Tech
                         pattern) — volume climbs while margin collapses as the
                         raised capital flows straight through; the public-intel
                         layer pairs it with a news pivot cluster, a website
                         cosine shift, and a co-occurring funding event
- name_cycling:          legal entity name change at month 6 (ZEFIX + WHOIS
                         signals fire) — the Mossack Fonseca shelf-cycling
                         pattern, where shelf companies are renamed to reset
                         KYC review clocks (Case 8 / re-KYC trigger)
- domain_pivot:          the public-facing business model changes (website +
                         WHOIS registrant) while transactions look superficially
                         normal — the Centra Tech pattern the AML profile misses

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
    "suspicious_stability",
    "dormancy_break",
    "news_spike",
    "pivot",
    "name_cycling",
    "domain_pivot",
)

# Synthetic onboarding vs current website text for the domain_pivot scenario.
# The two read as materially different businesses (boutique advisory → crypto
# exchange / token ICO — the Centra Tech pattern), so an offline embedder yields
# a cosine distance well above drift/business_model.py's 0.35 change threshold.
# Each clears the comparator's 50-char minimum so the comparison is never skipped
# as "empty_text". Used only in the offline demo path; live runs source these
# texts from the Wayback / Firecrawl adapters instead.
DOMAIN_PIVOT_ONBOARDING_TEXT = (
    "Helvetia Advisory AG is a boutique import and export consultancy based in "
    "Zug, advising family-owned manufacturers on cross-border trade finance, "
    "customs documentation, and supplier due diligence across the EU and UK."
)
DOMAIN_PIVOT_CURRENT_TEXT = (
    "HelvetiaX is a regulated cryptocurrency exchange and token launchpad "
    "offering spot trading, staking rewards, custodial wallets, and an initial "
    "coin offering for our new DeFi yield protocol with global onboarding."
)

# The name_cycling scenario (Case 8) injects a legal-entity name change at this
# month. Public ZEFIX + WHOIS signals are emitted here by the synthetic
# generator (see public_intel.generate_signals_for_customer) and the engine
# floors the drift score on the resulting `name_change` signal.
NAME_CHANGE_MONTH = 6

# Must match `assess_dormancy`'s `baseline_fraction` default (drift/dormancy.py):
# the dormancy_break scenario activates exactly on this split so the dormant
# baseline window stays clean.
DORMANCY_BASELINE_FRACTION = 0.5

# Country risk weights reused conceptually from the social-engineering extractor
CORRIDOR_RISK = {"CH": 0.05, "DE": 0.1, "IT": 0.15, "SG": 0.35, "HK": 0.4, "AE": 0.5, "RU": 0.95, "IR": 1.0}
LOW_RISK = ["CH", "DE", "IT"]
HIGH_RISK = ["RU", "IR", "AE"]


@dataclass
class SyntheticCustomer:
    drift_id: str
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
    # Website text at KYC onboarding (Wayback "before" reference) and the current
    # snapshot (Firecrawl "after"). Populated only for the domain_pivot scenario
    # in the offline demo; the business-model comparator diffs the two. None for
    # every other scenario, where no website comparison runs.
    onboarding_website_text: str | None = None
    current_website_text: str | None = None

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

    def days_per_month(self) -> int:
        """Daily observations per month window (uniform across months).

        Falls back to 21 (the simulator default) when the book has no volume
        data, so day<->month conversions never divide by zero.
        """
        if self.monthly_volume and len(self.monthly_volume[0]):
            return len(self.monthly_volume[0])
        return 21

    def day_to_month(self, day: int) -> int:
        """Map a daily index (e.g. a BOCPD changepoint) to its month window.

        The BOCPD detector runs over the concatenated daily volume series, so
        its changepoint is a day index; the drift timeline is indexed by month.
        """
        return day // self.days_per_month()


def generate_customer(
    drift_id: str,
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

    # Dormancy break must activate exactly at the dormancy detector's
    # baseline/active split (DORMANCY_BASELINE_FRACTION of the series); otherwise
    # an active month leaks into the baseline window and the depth factor clips
    # to 0. Snap the activation here so EVERY entry point — the demo book and the
    # live /drift/inject path — produces a flaggable customer regardless of the
    # caller's drift_start_month.
    if scenario == "dormancy_break":
        drift_start_month = round(months * DORMANCY_BASELINE_FRACTION)

    # The name change is a fixed-month event (Case 8). Pin it to NAME_CHANGE_MONTH
    # regardless of the caller's drift_start_month so every entry point — the demo
    # book and the live /drift/inject path — emits the name_change signal at the
    # same month the public signals fire. Clamp for unusually short books.
    if scenario == "name_cycling":
        drift_start_month = min(NAME_CHANGE_MONTH, months - 2)

    rng = np.random.default_rng(seed)
    # Causal ground-truth label: benign_expansion is the only benign drift;
    # suspicious_stability is its own category (the slow-walker / sleeper);
    # all other non-stable scenarios are risk.
    if scenario == "stable":
        causal_truth = None
    elif scenario == "benign_expansion":
        causal_truth = "benign"
    elif scenario == "suspicious_stability":
        causal_truth = "suspicious"
    else:
        # volume_creep / counterparty_migration / corridor_shift / combined /
        # dormancy_break / news_spike / pivot / name_cycling / domain_pivot are all risk-shaped.
        causal_truth = "risk"

    cust = SyntheticCustomer(
        drift_id=drift_id,
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
        if scenario == "dormancy_break":
            # The reactivated sleeper: near-floor volume for the whole dormant
            # baseline, then a HARD burst at activation (a step, not a creep) —
            # exactly the pattern the drift/velocity layers under-react to.
            if month < drift_start_month:
                vol_mean, vol_sd = 150.0, 30.0                 # dormant: quiet
            else:
                vol_mean, vol_sd = base_volume * 1.6, base_volume * 0.08  # surge
            volumes = rng.normal(vol_mean, vol_sd, days_per_month)
        else:
            # Both volume_creep (risk) AND benign_expansion move volume up by the
            # SAME magnitude — so velocity alone cannot tell them apart. The
            # causal layer distinguishes them by OTHER metrics (margin, etc.).
            vol_mult = 1.0
            if scenario in ("volume_creep", "combined", "benign_expansion", "news_spike", "pivot"):
                vol_mult = 1.0 + 1.2 * intensity  # up to +120% by the end
            # suspicious_stability: anomalously LOW noise — the slow-walker keeps
            # an unnaturally smooth profile. Real customers jitter (~15% daily
            # noise); a 2% profile is robotic and is itself the signal.
            vol_noise = 0.02 if scenario == "suspicious_stability" else 0.15
            volumes = rng.normal(base_volume * vol_mult, base_volume * vol_noise, days_per_month)
        volumes = np.maximum(volumes, 100.0)

        # --- Counterparty risk (share of tx with risky counterparties) ---
        base_risky_share = 0.05
        risky_share = base_risky_share
        if scenario in ("counterparty_migration", "combined"):
            risky_share = base_risky_share + 0.45 * intensity  # up to 50%
        # suspicious_stability: the ENVIRONMENT moves (counterparties drift
        # risky, as if the customer is being pulled into a network) even though
        # the customer's OWN volume stays robotically smooth. That mismatch is
        # the whole signal.
        if scenario == "suspicious_stability":
            risky_share = base_risky_share + 0.35 * intensity
        # name_cycling: the renamed shell quietly picks up new (riskier)
        # counterparties after the identity reset — a mild migration. Volume
        # stays flat; the identity change, not the volume, is the headline
        # signal (surfaced by the public name_change feed + the score floor).
        if scenario == "name_cycling":
            risky_share = base_risky_share + 0.30 * intensity
        # Benign expansion DIVERSIFIES (slightly more counterparties) but they
        # stay low-risk — share barely moves.
        cp_risk = rng.binomial(1, min(risky_share, 0.95), days_per_month).astype(float)
        cp_risk = cp_risk * rng.uniform(0.6, 1.0, days_per_month) + (1 - cp_risk) * rng.uniform(0.0, 0.15, days_per_month)

        # --- Corridor risk ---
        if scenario in ("corridor_shift", "combined"):
            p_high = 0.03 + 0.5 * intensity
        elif scenario == "suspicious_stability":
            p_high = 0.03 + 0.35 * intensity  # corridors shift while client calm
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
        if scenario in (
            "volume_creep", "counterparty_migration", "corridor_shift",
            "combined", "dormancy_break", "news_spike", "pivot", "name_cycling", "domain_pivot",
        ):
            # Risk: margin collapses toward 0 as intensity rises (the reactivated
            # shell — the pivoted ICO, or the silently-pivoted business — pushes
            # money straight through, near-zero retention). For domain_pivot this
            # is the only transactional tell; volume/counterparty/corridor stay at
            # baseline, so the public website/WHOIS change is what actually surfaces it.
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

    # domain_pivot carries onboarding vs current website text so the
    # business-model comparator can diff them (UC 9). The WHOIS registrant change
    # the scenario represents lands at drift_start_month; the website divergence
    # is the same pivot seen from the public side.
    if scenario == "domain_pivot":
        cust.onboarding_website_text = DOMAIN_PIVOT_ONBOARDING_TEXT
        cust.current_website_text = DOMAIN_PIVOT_CURRENT_TEXT

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
        "suspicious_stability": "Pavel Novak",
        # UC 1 — reputational risk. Kept LAST so the contagion-wired IDs
        # (drift-002, drift-004, drift-005) stay pinned to their scenarios.
        "news_spike": "Wirecard Holdings AG",
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
                drift_id=f"drift-{idx:03d}",
                name=name,
                scenario=scenario,
                seed=seed + idx,
            )
        )
        idx += 1
    # A second suspicious_stability customer (the "sleeper") — public signals
    # appear about him, but his transactions stay unnaturally calm. Shows a
    # different face of the same idea: reaction that doesn't match the world.
    book.append(
        generate_customer(
            drift_id=f"drift-{idx:03d}",
            name="Irina Volkova",
            scenario="suspicious_stability",
            seed=seed + 200,
        )
    )
    idx += 1
    # The reactivated sleeper (Case 7): a previously dormant shell that suddenly
    # begins high transaction volume. generate_customer snaps the activation to
    # the dormancy detector's baseline/active split, so it always flags.
    book.append(
        generate_customer(
            drift_id=f"drift-{idx:03d}",
            name="Dormant Holdings AG",
            scenario="dormancy_break",
            seed=seed + 300,
        )
    )
    idx += 1
    # The shelf-company cycler (Case 8): a legal entity that changes its name at
    # NAME_CHANGE_MONTH to reset its KYC review clock (Mossack Fonseca pattern).
    # ZEFIX + WHOIS public signals fire; the engine floors the drift score on the
    # resulting name_change signal so the identity reset surfaces for re-KYC.
    book.append(
        generate_customer(
            drift_id=f"drift-{idx:03d}",
            name="Meridian Trust Reg.",
            scenario="name_cycling",
            seed=seed + 400,
        )
    )
    idx += 1
    # The silent business-model pivot (Case 9): a boutique advisory whose website
    # and WHOIS registrant change into a crypto exchange while its transactions
    # look superficially normal — the Centra Tech pattern the AML profile misses.
    book.append(
        generate_customer(
            drift_id=f"drift-{idx:03d}",
            name="Helvetia Advisory AG",
            scenario="domain_pivot",
            seed=seed + 400,
        )
    )
    idx += 1
    for i in range(n_stable):
        book.append(
            generate_customer(
                drift_id=f"drift-{idx:03d}",
                name=stable_names[i % len(stable_names)],
                scenario="stable",
                seed=seed + idx,
            )
        )
        idx += 1
    return book
