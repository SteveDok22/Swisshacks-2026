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
    "jurisdiction_shift",
    "ownership_shift",
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

# The jurisdiction_shift scenario (UC7) injects a jurisdiction/legal-form change
# at this month. Public signals fire at this point and the engine floors the
# drift score on `jurisdiction_change` / `legal_form_change` signals (re-KYC=50).
JURISDICTION_CHANGE_MONTH = 6

# The ownership_shift scenario (UC8) injects a new beneficial owner at this month.
OWNERSHIP_CHANGE_MONTH = 7

# Must match `assess_dormancy`'s `baseline_fraction` default (drift/dormancy.py):
# the dormancy_break scenario activates exactly on this split so the dormant
# baseline window stays clean.
DORMANCY_BASELINE_FRACTION = 0.5

# Dormancy noise floor: pre-dormancy window uses this fraction of base_volume
# instead of near-zero so the dormant baseline is a realistic low-activity
# profile rather than a degenerate empty series.
DORMANCY_FLOOR_VOLUME = 0.05

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
    # Month at which the jurisdiction/legal-form change fires (jurisdiction_shift)
    jurisdiction_change_month: int | None = None
    # Month at which a new beneficial owner appears (ownership_shift)
    ownership_change_month: int | None = None
    # Public-facing domain for the live Wayback/Firecrawl/WHOIS path.
    domain: str | None = None
    # Sanctioned UBO name for the ownership_shift and combo scenarios.
    sanctioned_ubo_name: str | None = None
    # "synthetic" (default) → deterministic mock signals.
    # "live" → real external-API calls (cached to data/api_cache/).
    mode: str = "synthetic"

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
        # sanctions_month is deliberately left at the risk-scenario default
        # (final month) below: the name change at NAME_CHANGE_MONTH is a re-KYC
        # TRIGGER, not the sanctions event itself. Keeping the listing at the
        # final month gives the Time-Travel replay its strongest narrative — the
        # high-severity name_change public signal lifts the as-of score across the
        # alert threshold ~(months-1 - NAME_CHANGE_MONTH) months before the
        # listing, demonstrating the early-warning lead time. An earlier explicit
        # value would only shorten that lead time without any domain rationale.

    # The jurisdiction change is a fixed-month structural event (UC7). Pin it to
    # JURISDICTION_CHANGE_MONTH so the public signals and the re-KYC floor fire
    # at a consistent, reproducible point regardless of the caller's drift_start_month.
    if scenario == "jurisdiction_shift":
        drift_start_month = min(JURISDICTION_CHANGE_MONTH, months - 2)

    # The ownership change is a fixed-month structural event (UC8 new UBO). Pin
    # to OWNERSHIP_CHANGE_MONTH so public signals fire consistently.
    if scenario == "ownership_shift":
        drift_start_month = min(OWNERSHIP_CHANGE_MONTH, months - 2)

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
        # dormancy_break / news_spike / pivot / name_cycling / domain_pivot /
        # jurisdiction_shift / ownership_shift are all risk-shaped.
        causal_truth = "risk"

    cust = SyntheticCustomer(
        drift_id=drift_id,
        name=name,
        scenario=scenario,
        months=months,
        drift_start_month=None if scenario == "stable" else drift_start_month,
        sanctions_month=None if scenario in ("stable", "benign_expansion") else months - 1,
        causal_truth=causal_truth,
        jurisdiction_change_month=(
            drift_start_month if scenario == "jurisdiction_shift" else None
        ),
        ownership_change_month=(
            drift_start_month if scenario == "ownership_shift" else None
        ),
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
            # The reactivated sleeper: low-activity baseline (DORMANCY_FLOOR_VOLUME
            # of base_volume) for the whole dormant window, then a HARD burst at
            # activation (a step, not a creep) — exactly the pattern the
            # drift/velocity layers under-react to. Using a realistic noise floor
            # instead of near-zero keeps the dormant baseline non-degenerate.
            if month < drift_start_month:
                vol_mean = base_volume * DORMANCY_FLOOR_VOLUME
                vol_sd = vol_mean * 0.2  # tight noise on a quiet profile
            else:
                vol_mean, vol_sd = base_volume * 1.6, base_volume * 0.08  # surge
            volumes = rng.normal(vol_mean, vol_sd, days_per_month)
        else:
            # Both volume_creep (risk) AND benign_expansion move volume up by the
            # SAME magnitude — so velocity alone cannot tell them apart. The
            # causal layer distinguishes them by OTHER metrics (margin, etc.).
            # jurisdiction_shift and ownership_shift are STRUCTURAL changes only —
            # transaction profile stays normal; the drift is in the registry/UBO
            # data, surfaced by public signals.
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
        elif scenario in ("jurisdiction_shift", "ownership_shift"):
            # Structural-change scenarios: transactions stay normal — the drift is
            # purely in the registry/UBO data. Margin holds close to baseline;
            # only the public structural signals (jurisdiction_change,
            # ownership_change) and the re-KYC score floor identify the risk.
            margin_mean = base_margin * (1.0 - 0.05 * intensity)
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
    seed: int = 42,
) -> list[SyntheticCustomer]:
    """
    Generate the demo book: exactly 15 named entities covering all 10 AMINA use
    cases, plus 3 stable controls. Deterministic via seed.

    The cast is fixed (not parameterised by n_stable) so drift IDs are stable
    and all downstream references (contagion graph, test fixtures, seed.py) can
    rely on the 1-15 numbering without re-computing.
    """
    # fmt: off
    _CAST = [
        # (drift_id, name, scenario, domain, sanctioned_ubo_name, seed_offset)
        # --- flagged entities ---
        ("drift-001", "Helvetia Pharma Holding AG",    "news_spike",        "helvetia-pharma.ch",        None,                      1),
        ("drift-002", "Léman FX Trading SA",           "corridor_shift",    "leman-fx.ch",               None,                      2),
        ("drift-003", "Alpine Logistics Group AG",     "combined",          "alpine-logistics.ch",       None,                      3),
        ("drift-004", "Glarnisch Holding AG",          "name_cycling",      "glarnisch-holding.ch",      None,                      4),
        ("drift-005", "HelvetiaX",                     "domain_pivot",      "helvetiax.io",              None,                      5),
        ("drift-006", "Lattice Labs AG",               "pivot",             "lattice-labs.ch",           None,                      6),
        ("drift-007", "Rhône Capital GmbH",            "jurisdiction_shift","rhone-capital.ch",          None,                      7),
        ("drift-008", "Bernina Wealth Partners AG",    "ownership_shift",   "bernina-wealth.ch",         "ROSNEFT TRADING S.A.",    8),
        ("drift-009", "Nimbus Mobility AG",            "benign_expansion",  "nimbus-mobility.ch",        None,                      9),
        ("drift-010", "Säntis Import-Export AG",       "dormancy_break",    "saentis-import.ch",         None,                      10),
        ("drift-011", "Castor Trade Finance AG",       "combined",          "castor-trade.ch",           "ROSNEFT TRADING S.A.",    11),
        ("drift-012", "Engadin Capital SA",            "suspicious_stability","engadin-capital.ch",      None,                      12),
        # --- stable controls ---
        ("drift-013", "Zürisee Renewables AG",        "benign_expansion",  "zuerisee-renewables.ch",    None,                      13),
        ("drift-014", "Toggenburg Family Office",      "stable",            "toggenburg-fo.ch",          None,                      14),
        ("drift-015", "Vaud AgriTech SA",              "stable",            "vaud-agritech.ch",          None,                      15),
    ]
    # fmt: on

    book: list[SyntheticCustomer] = []
    for drift_id, name, scenario, domain, sanctioned_ubo, offset in _CAST:
        cust = generate_customer(
            drift_id=drift_id,
            name=name,
            scenario=scenario,
            seed=seed + offset,
        )
        cust.domain = domain
        cust.sanctioned_ubo_name = sanctioned_ubo
        book.append(cust)

    # --- Live entity: Temenos AG ---
    # Real Swiss banking-software company (SIX: TEMN). In 2023 Hindenburg
    # Research published an adverse short report; the CEO resigned weeks later.
    # GDELT and GLEIF calls for this entity are cached under data/api_cache/ and
    # committed to the repo so the demo works fully offline.
    temenos = generate_customer(
        drift_id="drift-live-001",
        name="Temenos AG",
        scenario="news_spike",
        seed=seed + 99,
    )
    temenos.domain = "temenos.com"
    temenos.mode = "live"
    book.append(temenos)

    # --- Live entity: Rosneft Trading S.A. (UC2 / UC5 / UC8) ---
    # A REAL OFAC/EU/SECO-listed entity (the same name seeded as the sanctioned
    # UBO on drift-008 / drift-011). In live mode the OpenSanctions adapter
    # screens the name against the live watchlist and returns a genuine,
    # clickable `sanctions` match (opensanctions.org/entities/<id>/), which the
    # SANCTIONS_SCORE_FLOOR escalates to critical — the cross-border sanctioned
    # counterparty pattern (Deutsche Bank mirror-trades / Danske Estonia). GLEIF
    # supplies the real ownership chain. Cached under data/api_cache/ for offline.
    rosneft = generate_customer(
        drift_id="drift-live-002",
        name="Rosneft Trading S.A.",
        scenario="corridor_shift",
        seed=seed + 100,
    )
    rosneft.mode = "live"
    book.append(rosneft)

    # --- Live entity: Wirecard AG (UC1 — negative-news spike) ---
    # The canonical adverse-media analogue from the roadmap. A real entity with a
    # real LEI; Event Registry returns real articles about the missing €1.9 B /
    # collapse, surfaced with their real titles and article URLs.
    wirecard = generate_customer(
        drift_id="drift-live-003",
        name="Wirecard AG",
        scenario="news_spike",
        seed=seed + 101,
    )
    wirecard.domain = "wirecard.com"
    wirecard.mode = "live"
    book.append(wirecard)

    # --- Live entity: WW International, Inc. (UC4/UC8 — legal name change) ---
    # Real entity whose GLEIF record carries PREVIOUS_LEGAL_NAME "Weight Watchers
    # International, Inc." -> "WW International, Inc." — a genuine, GLEIF-documented
    # rename that fires a real name_change signal (re-KYC floor) plus real news.
    ww = generate_customer(
        drift_id="drift-live-004",
        name="WW International, Inc.",
        scenario="name_cycling",
        seed=seed + 103,
    )
    ww.domain = "ww.com"
    ww.mode = "live"
    book.append(ww)

    # --- Live entity: Rosneft Deutschland GmbH (UC3/UC5 — sanctioned group) ---
    # Real German subsidiary whose GLEIF ultimate parent is OAO Rosneft Oil
    # Company (OFAC/EU-sanctioned). The entity itself is on the live OpenSanctions
    # list as part of the Rosneft group — a genuine "related business under
    # sanctions" example drawn entirely from real GLEIF + OpenSanctions data.
    rosneft_de = generate_customer(
        drift_id="drift-live-005",
        name="Rosneft Deutschland GmbH",
        scenario="combined",
        seed=seed + 104,
    )
    rosneft_de.mode = "live"
    book.append(rosneft_de)

    return book
