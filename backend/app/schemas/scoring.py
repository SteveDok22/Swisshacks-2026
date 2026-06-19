"""
Scoring schemas — what the ML pipeline accepts and returns.

The output structure is intentionally rich:
- score (numeric) for the UI
- level (categorical) for quick visual scanning
- confidence (probabilistic) for trust calibration
- features (top-N) for explainability
- recommendation (action) for the compliance officer

This response is what the frontend will render as a "case detail" view.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import DecisionAction, RiskLevel


class FeatureContribution(BaseModel):
    """
    Single feature's contribution to the score (one row in SHAP).
    
    Example:
        FeatureContribution(
            name="time_of_day_deviation",
            value=14.7,
            contribution=23.4,  # how much it pushed the score up
            direction="risk_increasing",
            human_label="Request outside typical hours (10pm vs usual 8am-6pm)",
        )
    """
    
    name: str = Field(..., description="Machine-readable feature name")
    value: float | str | None = Field(None, description="Actual feature value")
    contribution: float = Field(..., description="SHAP value — impact on final score")
    direction: str = Field(..., description="risk_increasing | risk_decreasing")
    human_label: str | None = Field(None, description="Plain-English description")


class RiskScoreResult(BaseModel):
    """
    Full output of a scoring run.
    
    Frontend uses this to render the entire case detail view:
    - top-level: score + level + confidence + recommendation
    - middle: top contributing features (SHAP)
    - bottom: model metadata for audit
    """
    
    # === Core score ===
    score: float = Field(..., ge=0, le=100, description="Risk score 0-100")
    level: RiskLevel
    confidence: float = Field(..., ge=0, le=1, description="Model confidence")
    
    # === Recommended action ===
    recommended_action: DecisionAction
    
    # === Explainability ===
    top_features: list[FeatureContribution] = Field(
        default_factory=list,
        description="Top features ranked by absolute contribution",
    )
    
    # === Metadata ===
    model_name: str
    model_version: str
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    
    # === Raw data (for debugging / audit, not shown in UI) ===
    raw_features: dict[str, Any] = Field(
        default_factory=dict,
        description="All extracted features (for audit)",
    )


class ScoringRequest(BaseModel):
    """Request to score a specific case."""
    
    case_id: UUID
    force_rescore: bool = Field(
        False,
        description="Re-run scoring even if case already has a score",
    )


class ScoringResponse(BaseModel):
    """Response from scoring endpoint."""
    
    case_id: UUID
    result: RiskScoreResult
