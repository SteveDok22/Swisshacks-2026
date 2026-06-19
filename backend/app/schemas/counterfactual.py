"""
Counterfactual schemas.

Counterfactuals answer the question:
"What minimal change would flip the decision?"

Example output:
    "If amount were CHF 800K (instead of 4.5M),
     and hour were 10am (instead of 8pm),
     this would be approved."
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeatureChange(BaseModel):
    """A single feature change in a counterfactual."""
    
    feature: str = Field(..., description="Feature name")
    original_value: Any = Field(..., description="Current value")
    counterfactual_value: Any = Field(..., description="Value that would flip decision")
    change_description: str = Field(..., description="Human-readable change")


class Counterfactual(BaseModel):
    """One counterfactual scenario."""
    
    scenario_id: int
    new_predicted_outcome: str = Field(
        ..., description="What the model would predict (e.g., 'low_risk')"
    )
    changes: list[FeatureChange]
    summary: str = Field(..., description="One-sentence explanation")


class CounterfactualResponse(BaseModel):
    """Full counterfactual analysis for a case."""
    
    case_id: str
    original_score: float
    original_outcome: str
    counterfactuals: list[Counterfactual]
    notes: str | None = None
