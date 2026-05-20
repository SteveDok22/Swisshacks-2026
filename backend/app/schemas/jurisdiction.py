"""Schemas for jurisdiction-specific rule packs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TravelRuleConfig(BaseModel):
    threshold_chf: float
    required_fields: list[str]


class CDDConfig(BaseModel):
    enhanced_due_diligence_threshold_chf: float
    ongoing_review_max_days: int
    pep_review_max_days: int


class ActionThresholds(BaseModel):
    allow_max: float
    step_up_max: float
    escalate_max: float


class ReportingConfig(BaseModel):
    fiu_threshold_chf: float | None = None
    mros_threshold_chf: float | None = None
    jfiu_threshold_chf: float | None = None
    suspicious_activity_24h: bool = False
    suspicious_activity_max_days: int | None = None


class JurisdictionRules(BaseModel):
    """Full rule pack for one jurisdiction (loaded from YAML)."""
    
    code: str
    name: str
    regulator: str
    description: str
    
    travel_rule: TravelRuleConfig
    cdd: CDDConfig
    score_modifiers: dict[str, float] = Field(default_factory=dict)
    action_thresholds: ActionThresholds
    reporting: ReportingConfig
    officer_notes: str


class JurisdictionAdjustedScore(BaseModel):
    """Result of applying jurisdiction rules to a base ML score."""
    
    jurisdiction_code: str
    jurisdiction_name: str
    
    base_score: float
    adjusted_score: float
    
    modifiers_applied: dict[str, float] = Field(default_factory=dict)
    recommended_action: str
    
    applicable_rules: list[str] = Field(default_factory=list)
    officer_notes: str
