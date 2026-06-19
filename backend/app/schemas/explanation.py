"""
Explanation schemas — natural language outputs for compliance officers.

Two types of explanations:
1. CaseSummary — full narrative covering score, top features, counterfactuals
2. QuickAssessment — one-paragraph executive summary

Both go through the same pipeline:
ML score → SHAP → Counterfactuals → Anonymizer → Claude → human-readable text
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExplanationMetadata(BaseModel):
    """Metadata about how the explanation was generated."""
    
    model: str = Field(..., description="Claude model used")
    anonymization_applied: bool = Field(
        True,
        description="True if PII was anonymized before LLM call",
    )
    fields_redacted_count: int = 0
    fields_bucketed_count: int = 0
    cached: bool = Field(
        False,
        description="True if response was served from cache",
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CaseExplanation(BaseModel):
    """
    Full natural language explanation for a case.
    
    What the compliance officer reads in the UI.
    """
    
    case_id: str
    
    # The narrative parts
    executive_summary: str = Field(
        ...,
        description="One-paragraph TL;DR for the compliance officer",
    )
    risk_factors: str = Field(
        ...,
        description="Detailed walkthrough of WHY this scored as it did",
    )
    alternative_outcomes: str | None = Field(
        None,
        description="Counterfactual narrative (only if case is high-risk)",
    )
    recommended_action_rationale: str = Field(
        ...,
        description="Why we recommend allow/escalate/block",
    )
    jurisdiction_notes: str | None = Field(
        None,
        description="Jurisdiction-specific compliance requirements",
    )
    
    metadata: ExplanationMetadata


class AnonymizationPreview(BaseModel):
    """
    Shows what data goes to AI vs what stays local.
    Critical UI feature for FINMA compliance demonstration.
    """
    
    fields_kept_local: list[str]
    fields_sent_to_ai: dict[str, str]  # field_name → anonymized_value
    fields_redacted: list[str]
    fields_bucketed: list[str]


class ExplanationStreamChunk(BaseModel):
    """
    Single chunk in a streaming explanation response (SSE).
    
    Frontend will progressively append `text` to its display.
    """
    
    chunk_type: Literal["text", "metadata", "done", "error"]
    text: str = ""
    metadata: dict | None = None
