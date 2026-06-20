"""
Audit log schemas.

Three key shapes:
- AuditEntry — full record returned from queries
- DecisionCreate — what a compliance officer submits when acting on a case
  (case-review workflow) or a drift customer (drift-engine workflow)
- DecisionRead — what we return after recording
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import DecisionAction


# === Audit Entry ===

class AuditEntryRead(BaseModel):
    """A single audit log entry."""
    
    id: UUID
    event_type: str
    case_id: UUID | None = None
    client_id: UUID | None = None
    drift_id: str | None = None
    actor_id: str | None = None
    actor_type: str
    payload: dict[str, Any]
    risk_score: float | None = None
    risk_level: str | None = None
    occurred_at: datetime


class AuditQueryParams(BaseModel):
    """Query parameters for filtering audit log."""
    
    event_type: str | None = None
    case_id: UUID | None = None
    client_id: UUID | None = None
    drift_id: str | None = None
    actor_id: str | None = None
    risk_level: str | None = None
    
    from_date: datetime | None = None
    to_date: datetime | None = None
    
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


# === Decision ===

class DecisionCreate(BaseModel):
    """Schema for compliance officer recording a decision.

    Exactly one of ``case_id`` or ``drift_id`` must be provided:
    - ``case_id`` — traditional case-review workflow
    - ``drift_id`` — drift-engine workflow (no linked case record)

    Drift recommendations are always derived by the backend.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: UUID | None = None
    drift_id: str | None = Field(None, min_length=1, max_length=255)
    action: DecisionAction
    officer_id: str = Field(..., description="Identifier of the deciding officer")
    rationale: str | None = Field(
        None,
        min_length=10,
        max_length=2000,
        description="Required if overriding AI recommendation",
    )
    @field_validator("drift_id", "officer_id", "rationale", mode="before")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _exactly_one_id(self) -> "DecisionCreate":
        has_case = self.case_id is not None
        has_customer = self.drift_id is not None
        if not has_case and not has_customer:
            raise ValueError("Provide either case_id or drift_id")
        if has_case and has_customer:
            raise ValueError("Provide either case_id or drift_id, not both")
        return self


class DecisionRead(BaseModel):
    """Schema for returning a recorded decision."""

    id: UUID
    case_id: UUID | None = None
    drift_id: str | None = None
    action: DecisionAction
    officer_id: str
    rationale: str | None = None

    overrode_ai: bool
    ai_recommended_action: DecisionAction | None = None
    ai_risk_score: float | None = None
    ai_risk_level: str | None = None
    analysis_snapshot: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime
