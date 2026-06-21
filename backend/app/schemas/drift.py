"""Pydantic schemas for the Drift Engine API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import DecisionAction


class LayerContribution(BaseModel):
    """One signal layer's contribution to the drift score."""

    layer: int = Field(description="Layer number 1-7")
    name: str = Field(description="Human-readable layer name")
    llr: float = Field(description="Log-likelihood ratio contribution")
    status: str = Field(description="ok | notable | deviation | pending")
    detail: str | None = Field(default=None, description="Human-readable explanation")


class PublicSignalOut(BaseModel):
    """One external public-intelligence signal."""

    month: int
    signal_type: str = Field(description="news | sanctions | adverse_media | ownership_change | funding_event")
    headline: str
    severity: float = Field(description="0-1 classifier severity")
    source: str
    source_url: str | None = Field(default=None, description="Deep-link to the original source record")
    corroborated: bool = Field(
        default=False,
        description=(
            "True when a business_model_change pivot was lifted to the critical band by "
            "two independent sources (news event cluster + website cosine shift, UC 10)"
        ),
    )


class UboScreeningOut(BaseModel):
    """One UBO / ownership-chain entity screened against sanctions watchlists.

    Case 5 (new shareholders / UBOs): the aggregator resolves the customer's
    GLEIF ownership chain to names and screens each through OpenSanctions. A hit
    above the match-score floor surfaces here with the screened name, the matched
    watchlist entity, and the match score.
    """

    screened_ubo: str = Field(description="UBO / officer name screened (resolved from the GLEIF ownership chain)")
    matched_entity: str = Field(description="Watchlist entity the UBO matched")
    score: float = Field(description="OpenSanctions match score 0-1")
    severity: float = Field(description="Signal severity 0-1")
    month: int
    definitive: bool = Field(default=False, description="True when score >= 0.85 (definitive); False = probable, manual confirmation")
    source_url: str | None = Field(default=None, description="Deep-link to the matched watchlist record")


class CausalVerdictOut(BaseModel):
    """Causal hypothesis competition: is the drift risk-shaped or life-shaped?"""

    causal_llr: float = Field(description="log P(O|risk)/P(O|benign); >0 = risk-shaped")
    p_risk: float = Field(description="Posterior P(risk | signature), 0-1")
    label: str = Field(description="risk | benign | ambiguous")
    # Signature: how each metric moved
    volume_change: float
    margin_change: float
    counterparty_change: float
    corridor_change: float
    # Per-metric LLR contributions (which metric drove the verdict)
    contributions: dict[str, float] = Field(default_factory=dict)


class StabilityOut(BaseModel):
    """Suspicious-stability assessment: the slow-walker / sleeper detector."""

    suspicion: float = Field(description="0-1 product of the two factors")
    stability_anomaly: float = Field(description="0-1 how unnaturally smooth")
    environmental_movement: float = Field(description="0-1 how much surroundings move")
    own_volatility: float = Field(description="subject coefficient of variation")
    cohort_volatility: float = Field(description="cohort median CV (reference)")
    is_suspicious: bool
    detail: str


class DormancyOut(BaseModel):
    """Dormancy-break assessment: the sleeper-account reactivation detector."""

    dormancy_break: float = Field(description="0-1 product of the two factors")
    dormancy_depth: float = Field(description="0-1 how dormant the baseline was")
    activation_strength: float = Field(description="0-1 how strong the later burst is")
    baseline_volume: float = Field(description="mean volume in the dormant window")
    active_volume: float = Field(description="mean volume in the active window")
    is_dormancy_break: bool
    detail: str


class AsOfPointOut(BaseModel):
    """The score the system WOULD have produced at month T, using only data
    available up to T (no look-ahead)."""

    month: int
    as_of_score: float
    velocity: float
    public_risk: float
    contagion_active: bool
    causal_p_risk: float


class ReplayResult(BaseModel):
    """Time-Travel Audit: full as-of replay proving no look-ahead bias."""

    drift_id: str
    name: str
    points: list[AsOfPointOut]
    alert_month: int | None
    sanctions_month: int | None
    lead_time_months: int | None
    alert_threshold: float


class DriftSubjectSummary(BaseModel):
    """Book-overview row: one drift subject's snapshot."""

    drift_id: str
    name: str
    drift_score: float = Field(description="0-100 fused drift score")
    drift_velocity: float = Field(description="bits/month, latest")
    velocity_band: str = Field(description="natural | notable | structural | rapid")
    reached_tier: str = Field(description="Cascade tier reached")
    sanctions_hit: bool = False
    propagated_risk: float = Field(default=0.0, description="Layer 3 contagion risk")
    public_risk: float = Field(default=0.0, description="Layer 2 public intelligence risk")
    confirmation_lift: float = Field(default=1.0, description="Public-internal co-occurrence lift")
    causal_label: str = Field(default="ambiguous", description="risk | benign | ambiguous")
    causal_p_risk: float = Field(default=0.5, description="Posterior P(risk)")
    suspicion: float = Field(default=0.0, description="Suspicious-stability score 0-1")
    is_suspicious: bool = Field(default=False, description="Slow-walker flag")
    dormancy_break: float = Field(default=0.0, description="Dormancy-break score 0-1")
    is_dormancy_break: bool = Field(default=False, description="Suspicious-activation flag")
    is_name_changed: bool = Field(default=False, description="Confirmed legal-entity name change (re-KYC trigger, UC8)")
    risk_level: str = Field(default="low", description="critical | high | medium | low — fused score bracket")
    scenario: str | None = Field(default=None, description="Ground-truth scenario (demo)")
    mode: str = Field(default="synthetic", description="synthetic | live — whether signals come from cached real API calls")


class DriftTimelinePoint(BaseModel):
    """One month in a drift subject's timeline (the scrubber data)."""

    month: int
    drift_bits: float
    velocity: float
    acceleration: float
    bocpd_changepoint: bool = False


class DriftSubjectDetail(BaseModel):
    """Full drift analysis for one drift subject."""

    drift_id: str
    name: str
    drift_score: float
    drift_velocity: float
    velocity_band: str
    reached_tier: str
    recommended_action: DecisionAction
    risk_level: str
    escalation_reasons: list[str] = Field(default_factory=list)
    layers: list[LayerContribution] = Field(default_factory=list)
    timeline: list[DriftTimelinePoint] = Field(default_factory=list)
    # Demo ground truth
    scenario: str | None = None
    mode: str = Field(default="synthetic", description="synthetic | live — real cached API data")
    drift_start_month: int | None = None
    sanctions_month: int | None = None
    bocpd_changepoint_day: int | None = None
    # News-volume regime change (UC 1): the month a sustained news spike broke,
    # detected by BOCPD over the weekly event-count series. Anchors the public
    # side of the confirmation-lift window. None when no spike is found (or there
    # are no public signals).
    news_spike_month: int | None = None

    # Two-layer breakdown (AMINA Challenge 4 architecture)
    public_risk: float = Field(default=0.0, description="Public intelligence layer risk 0-1")
    internal_risk: float = Field(default=0.0, description="Internal bank data layer risk 0-1")
    confirmation_lift: float = Field(default=1.0, description="Temporal co-occurrence amplification")
    public_signals: list[PublicSignalOut] = Field(default_factory=list)
    # Case 5: UBO / ownership-chain sanctions screening hits (matched names + scores).
    ubo_screening: list[UboScreeningOut] = Field(default_factory=list)

    # UC8: confirmed legal-entity name change (re-KYC trigger). Mirrors the
    # summary flag so the detail panel can surface the identity-reset treatment
    # without re-deriving it from the public-signals list. The underlying
    # `name_change` (ZEFIX/GLEIF) and `domain_change` (WHOIS) signals that set
    # this flag also flow through `public_signals` above.
    is_name_changed: bool = Field(
        default=False,
        description="Confirmed legal-entity name change (re-KYC trigger, UC8); floors the drift score at 60",
    )

    # Business-model drift (UC 9): silent website/domain pivot since onboarding.
    # Derived from the Wayback (onboarding) vs Firecrawl (current) website-text
    # cosine comparison in drift/business_model.py. When no website texts are
    # available or the embeddings backend is absent, the comparison is skipped and
    # these stay at their neutral defaults (no change, distance 0.0).
    is_business_model_change: bool = Field(
        default=False,
        description="True when the public-facing business model shifted materially since onboarding",
    )
    business_model_distance: float = Field(
        default=0.0,
        description="Cosine distance between onboarding and current website text (0 = identical, higher = more divergent)",
    )
    # UC9 website-diff evidence for the side-by-side panel. Texts are the actual
    # onboarding (Wayback) vs current (Firecrawl) website content; the URLs link
    # to the archived snapshot and the live site; the summary is a one-line
    # plain-language explanation of what changed.
    onboarding_website_text: str | None = None
    current_website_text: str | None = None
    onboarding_website_url: str | None = None
    current_website_url: str | None = None
    business_model_summary: str | None = Field(
        default=None,
        description="One short LLM summary of how the website changed (onboarding vs now)",
    )

    # Causal drift: risk-shaped vs life-shaped change
    causal: CausalVerdictOut | None = None

    # Suspicious stability: the slow-walker / sleeper detector
    stability: StabilityOut | None = None

    # Dormancy break: the reactivated-sleeper / suspicious-activation detector
    dormancy: DormancyOut | None = None


class LLMAdjudicationOut(BaseModel):
    """One T2 LLM adjudication executed during a drift scan."""

    drift_id: str
    drift_name: str
    llm_mode: str = Field(description="real | mock")
    was_cached: bool = False
    tokens_used: int = Field(default=0, description="Input+output tokens consumed; 0 for mock or cached calls")
    response: dict[str, Any] = Field(default_factory=dict)


class CascadeCostReport(BaseModel):
    """Cost-cascade report for a scan pass."""

    total_customers: int
    tier_counts: dict[str, int]
    tier_costs: dict[str, float]
    total_cost: float
    summary: str
    # Comparison baseline
    llm_on_everything_cost: float
    savings_pct: float
    actual_t2_llm_calls: int = 0
    real_t2_llm_calls: int = 0
    mock_t2_llm_calls: int = 0
    # Token usage tracking (populated from real API calls; 0 in mock/cached mode)
    tokens_used: int = Field(default=0, description="Total input+output tokens consumed across all T2 LLM calls in this scan")
    model: str | None = Field(default=None, description="Model used for T2 adjudication; None when all calls were mock or cached")
    llm_adjudications: list[LLMAdjudicationOut] = Field(default_factory=list)


class ContagionNode(BaseModel):
    id: str
    name: str
    is_customer: bool
    entity_type: str
    risk: float
    hops_from_seed: int | None = None
    is_seed: bool = False


class ContagionEdge(BaseModel):
    source: str
    target: str
    stake: float


class ContagionGraph(BaseModel):
    """Ownership graph for visualization, with propagated risk."""

    nodes: list[ContagionNode]
    edges: list[ContagionEdge]
    seeds: list[str] = Field(default_factory=list)


class InjectScenarioRequest(BaseModel):
    """Red-team: inject a synthetic drift scenario."""

    scenario: str = Field(
        default="combined",
        description=(
            "stable | volume_creep | counterparty_migration | corridor_shift | "
            "combined | benign_expansion | suspicious_stability | dormancy_break | "
            "domain_pivot"
        ),
    )
    name: str = Field(default="Injected Test Customer")


class RFIResponse(BaseModel):
    """Value-of-Information ranked request-for-information (Layer 7)."""

    drift_id: str
    questions: list[str]
    rationale: str
    estimated_info_gain_bits: float
