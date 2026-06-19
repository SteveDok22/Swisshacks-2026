"""Pydantic schemas for the Drift Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class DriftCustomerSummary(BaseModel):
    """Book-overview row: one customer's drift snapshot."""

    customer_id: str
    name: str
    drift_score: float = Field(description="0-100 fused drift score")
    drift_velocity: float = Field(description="bits/month, latest")
    velocity_band: str = Field(description="natural | notable | structural | rapid")
    reached_tier: str = Field(description="Cascade tier reached")
    sanctions_hit: bool = False
    propagated_risk: float = Field(default=0.0, description="Layer 3 contagion risk")
    public_risk: float = Field(default=0.0, description="Layer 2 public intelligence risk")
    confirmation_lift: float = Field(default=1.0, description="Public-internal co-occurrence lift")
    scenario: str | None = Field(default=None, description="Ground-truth scenario (demo)")


class DriftTimelinePoint(BaseModel):
    """One month in a customer's drift timeline (the scrubber data)."""

    month: int
    drift_bits: float
    velocity: float
    acceleration: float
    bocpd_changepoint: bool = False


class DriftCustomerDetail(BaseModel):
    """Full drift analysis for one customer."""

    customer_id: str
    name: str
    drift_score: float
    drift_velocity: float
    velocity_band: str
    reached_tier: str
    escalation_reasons: list[str] = Field(default_factory=list)
    layers: list[LayerContribution] = Field(default_factory=list)
    timeline: list[DriftTimelinePoint] = Field(default_factory=list)
    # Demo ground truth
    scenario: str | None = None
    drift_start_month: int | None = None
    sanctions_month: int | None = None
    bocpd_changepoint_day: int | None = None

    # Two-layer breakdown (AMINA Challenge 4 architecture)
    public_risk: float = Field(default=0.0, description="Public intelligence layer risk 0-1")
    internal_risk: float = Field(default=0.0, description="Internal bank data layer risk 0-1")
    confirmation_lift: float = Field(default=1.0, description="Temporal co-occurrence amplification")
    public_signals: list[PublicSignalOut] = Field(default_factory=list)


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
        description="stable | volume_creep | counterparty_migration | corridor_shift | combined",
    )
    name: str = Field(default="Injected Test Customer")


class RFIResponse(BaseModel):
    """Value-of-Information ranked request-for-information (Layer 7)."""

    customer_id: str
    questions: list[str]
    rationale: str
    estimated_info_gain_bits: float
