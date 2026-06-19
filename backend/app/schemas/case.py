"""
Case schemas — the central unit of review.

A "case" is anything that needs human-in-the-loop decision:
- AMINA: suspicious transaction request via voice call
- JB: investment recommendation requiring suitability check
- Ripple: incoming XRPL transaction requiring AML review
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import IdentifiedModel
from app.schemas.enums import CaseStatus, CaseType, Jurisdiction


class CaseContext(BaseModel):
    """
    Flexible context payload for a case.
    
    Different case types put different things here:
    - SOCIAL_ENGINEERING: voice_sample_url, transcript, requested_amount
    - INVESTMENT_RECOMMENDATION: portfolio_snapshot, requested_products
    - XRPL_TRANSACTION: tx_hash, from_address, to_address, amount, asset
    
    Using `dict[str, Any]` here because the structure varies per case_type.
    The frontend knows what to expect based on case_type.
    """
    
    summary: str = Field(..., description="One-line human-readable description")
    data: dict[str, Any] = Field(default_factory=dict)


class CaseBase(BaseModel):
    """Shared fields for case create/read."""
    
    client_id: UUID
    case_type: CaseType
    jurisdiction: Jurisdiction
    context: CaseContext


class CaseCreate(CaseBase):
    """Input schema for creating a case."""
    pass


class Case(IdentifiedModel, CaseBase):
    """Full case entity stored in the system."""
    
    status: CaseStatus = CaseStatus.PENDING
    
    # Filled in after ML scoring runs
    risk_score: float | None = Field(None, ge=0, le=100)
    risk_level: str | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    
    # Assignment for review
    assigned_to: str | None = None
    
    # Timing
    scored_at: datetime | None = None
    resolved_at: datetime | None = None


class CaseRead(BaseModel):
    """Output schema for API responses."""
    
    id: UUID
    client_id: UUID
    case_type: CaseType
    jurisdiction: Jurisdiction
    status: CaseStatus
    context: CaseContext
    
    risk_score: float | None = None
    risk_level: str | None = None
    confidence: float | None = None
    
    assigned_to: str | None = None
    created_at: datetime
    scored_at: datetime | None = None
    resolved_at: datetime | None = None


class CaseListItem(BaseModel):
    """
    Compact case representation for list views.
    
    Why separate from CaseRead:
    - List endpoints return many items — keep payload small
    - Detail view returns CaseRead with full context
    """
    
    id: UUID
    case_type: CaseType
    jurisdiction: Jurisdiction
    status: CaseStatus
    summary: str
    risk_score: float | None = None
    risk_level: str | None = None
    created_at: datetime
