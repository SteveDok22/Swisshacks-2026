"""
Audit log schemas.

Two key shapes:
- AuditEntry — full record returned from queries
- DecisionCreate — what compliance officer submits when acting on a case
- DecisionRead — what we return after recording
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import DecisionAction


# === Audit Entry ===

class AuditEntryRead(BaseModel):
    """A single audit log entry."""
    
    id: UUID
    event_type: str
    case_id: UUID | None = None
    client_id: UUID | None = None
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
    actor_id: str | None = None
    risk_level: str | None = None
    
    from_date: datetime | None = None
    to_date: datetime | None = None
    
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


# === Decision ===

class DecisionCreate(BaseModel):
    """Schema for compliance officer recording a decision."""
    
    case_id: UUID
    action: DecisionAction
    officer_id: str = Field(..., description="Identifier of the deciding officer")
    rationale: str | None = Field(
        None,
        description="Required if overriding AI recommendation",
    )


class DecisionRead(BaseModel):
    """Schema for returning a recorded decision."""
    
    id: UUID
    case_id: UUID
    action: DecisionAction
    officer_id: str
    rationale: str | None = None
    
    overrode_ai: bool
    ai_recommended_action: DecisionAction | None = None
    ai_risk_score: float | None = None
    ai_risk_level: str | None = None
    
    created_at: datetime
