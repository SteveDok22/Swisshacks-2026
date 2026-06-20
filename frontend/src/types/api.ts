/**
 * TypeScript types mirroring the backend Pydantic schemas.
 *
 * Keep in sync with backend/app/schemas/.
 * These give us full autocomplete + type safety against the API.
 */

// === Enums ===
export type Jurisdiction = "CH" | "EU" | "HK" | "AE";

export type CaseType =
  | "social_engineering"
  | "portfolio_risk"
  | "investment_recommendation"
  | "client_onboarding"
  | "xrpl_transaction";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type DecisionAction =
  | "allow"
  | "step_up_verification"
  | "escalate"
  | "block";

export type CaseStatus = "pending" | "in_review" | "resolved" | "expired";

// === Case ===
export interface CaseContext {
  summary: string;
  data: Record<string, unknown>;
}

export interface CaseListItem {
  id: string;
  case_type: CaseType;
  jurisdiction: Jurisdiction;
  status: CaseStatus;
  summary: string;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  created_at: string;
}

export interface CaseDetail {
  id: string;
  client_id: string;
  case_type: CaseType;
  jurisdiction: Jurisdiction;
  status: CaseStatus;
  context: CaseContext;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  confidence: number | null;
  assigned_to: string | null;
  created_at: string;
  scored_at: string | null;
  resolved_at: string | null;
}

// === Scoring ===
export interface FeatureContribution {
  name: string;
  value: number | string | null;
  contribution: number;
  direction: "risk_increasing" | "risk_decreasing";
  human_label: string | null;
}

export interface RiskScoreResult {
  score: number;
  level: RiskLevel;
  confidence: number;
  recommended_action: DecisionAction;
  top_features: FeatureContribution[];
  model_name: string;
  model_version: string;
  scored_at: string;
}

export interface ScoringResponse {
  case_id: string;
  result: RiskScoreResult;
}

// === Counterfactuals ===
export interface FeatureChange {
  feature: string;
  original_value: unknown;
  counterfactual_value: unknown;
  change_description: string;
}

export interface Counterfactual {
  scenario_id: number;
  new_predicted_outcome: string;
  changes: FeatureChange[];
  summary: string;
}

export interface CounterfactualResponse {
  case_id: string;
  original_score: number;
  original_outcome: string;
  counterfactuals: Counterfactual[];
  notes: string | null;
}

// === Explanation ===
export interface ExplanationMetadata {
  model: string;
  anonymization_applied: boolean;
  fields_redacted_count: number;
  fields_bucketed_count: number;
  cached: boolean;
  generated_at: string;
}

export interface CaseExplanation {
  case_id: string;
  executive_summary: string;
  risk_factors: string;
  alternative_outcomes: string | null;
  recommended_action_rationale: string;
  jurisdiction_notes: string | null;
  metadata: ExplanationMetadata;
}

export interface AnonymizationPreview {
  fields_kept_local: string[];
  fields_sent_to_ai: Record<string, string>;
  fields_redacted: string[];
  fields_bucketed: string[];
}

// === Jurisdiction comparison ===
export interface JurisdictionAdjustedScore {
  jurisdiction_code: string;
  jurisdiction_name: string;
  base_score: number;
  adjusted_score: number;
  modifiers_applied: Record<string, number>;
  recommended_action: string;
  applicable_rules: string[];
  officer_notes: string;
}

// === Client ===
export interface ClientProfile {
  full_name: string;
  email: string | null;
  primary_jurisdiction: Jurisdiction;
  risk_tolerance: string;
  aum_chf: number;
  esg_focus: boolean;
  is_pep: boolean;
  preferred_asset_classes: string[];
}

export interface Client {
  id: string;
  profile: ClientProfile;
  created_at: string;
}

// === Audit ===
export interface AuditEntry {
  id: string;
  event_type: string;
  case_id: string | null;
  client_id: string | null;
  drift_id: string | null;
  actor_id: string | null;
  actor_type: string;
  payload: Record<string, unknown>;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  occurred_at: string;
}

// === Decisions ===
export interface DecisionRead {
  id: string;
  case_id: string | null;
  drift_id: string | null;
  action: DecisionAction;
  officer_id: string;
  rationale: string | null;
  overrode_ai: boolean;
  ai_recommended_action: DecisionAction | null;
  ai_risk_score: number | null;
  ai_risk_level: RiskLevel | null;
  analysis_snapshot: Record<string, unknown>;
  created_at: string;
}

// === Pagination wrapper ===
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// === Drift Engine (AMINA Challenge 4) ===



export interface CausalVerdict {
  causal_llr: number;
  p_risk: number;
  label: string;
  volume_change: number;
  margin_change: number;
  counterparty_change: number;
  corridor_change: number;
  contributions: Record<string, number>;
}


export interface StabilityVerdict {
  suspicion: number;
  stability_anomaly: number;
  environmental_movement: number;
  own_volatility: number;
  cohort_volatility: number;
  is_suspicious: boolean;
  detail: string;
}


export interface AsOfPoint {
  month: number;
  as_of_score: number;
  velocity: number;
  public_risk: number;
  contagion_active: boolean;
  causal_p_risk: number;
}

export interface ReplayResult {
  drift_id: string;
  name: string;
  points: AsOfPoint[];
  alert_month: number | null;
  sanctions_month: number | null;
  lead_time_months: number | null;
  alert_threshold: number;
}

export interface PublicSignal {
  month: number;
  signal_type: string;
  headline: string;
  severity: number;
  source: string;
  source_url: string | null;
}

export interface LayerContribution {
  layer: number;
  name: string;
  llr: number;
  status: string;
  detail: string | null;
}

export interface DriftCustomerSummary {
  drift_id: string;
  name: string;
  drift_score: number;
  drift_velocity: number;
  velocity_band: string;
  reached_tier: string;
  sanctions_hit: boolean;
  propagated_risk: number;
  public_risk: number;
  confirmation_lift: number;
  causal_label: string;
  causal_p_risk: number;
  suspicion: number;
  is_suspicious: boolean;
  scenario: string | null;
}

export interface DriftTimelinePoint {
  month: number;
  drift_bits: number;
  velocity: number;
  acceleration: number;
  bocpd_changepoint: boolean;
}

export interface DriftCustomerDetail {
  drift_id: string;
  name: string;
  drift_score: number;
  drift_velocity: number;
  velocity_band: string;
  reached_tier: string;
  recommended_action: DecisionAction;
  risk_level: RiskLevel;
  escalation_reasons: string[];
  layers: LayerContribution[];
  timeline: DriftTimelinePoint[];
  scenario: string | null;
  drift_start_month: number | null;
  sanctions_month: number | null;
  bocpd_changepoint_day: number | null;
  public_risk: number;
  internal_risk: number;
  confirmation_lift: number;
  public_signals: PublicSignal[];
  causal: CausalVerdict | null;
  stability: StabilityVerdict | null;
}

export interface CascadeCostReport {
  total_customers: number;
  tier_counts: Record<string, number>;
  tier_costs: Record<string, number>;
  total_cost: number;
  summary: string;
  llm_on_everything_cost: number;
  savings_pct: number;
  actual_t2_llm_calls: number;
  real_t2_llm_calls: number;
  mock_t2_llm_calls: number;
  llm_adjudications: LLMAdjudication[];
}

export interface LLMAdjudication {
  drift_id: string;
  drift_name: string;
  llm_mode: "real" | "mock";
  was_cached: boolean;
  response: {
    verdict: "risk" | "benign" | "ambiguous";
    confidence: number;
    rationale: string;
    key_evidence: string[];
    recommended_action: string;
  };
}

export interface ContagionNode {
  id: string;
  name: string;
  is_customer: boolean;
  entity_type: string;
  risk: number;
  hops_from_seed: number | null;
  is_seed: boolean;
}

export interface ContagionEdge {
  source: string;
  target: string;
  stake: number;
}

export interface ContagionGraphData {
  nodes: ContagionNode[];
  edges: ContagionEdge[];
  seeds: string[];
}
