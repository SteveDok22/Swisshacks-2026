"""
Database models (SQLModel).

Design decisions:

1. SEPARATE from Pydantic API schemas (app/schemas/)
   - API schemas describe request/response shapes
   - DB models describe storage layout
   - This lets us change one without breaking the other

2. JSON columns for flexible data
   - case.context.data and client.profile contain heterogeneous
     fields per case_type. We store these as JSON columns.
   - Trade-off: less queryable, but much more flexible for an MVP

3. Audit log is APPEND-ONLY
   - No update or delete methods
   - All decisions, scorings, and overrides are logged immutably
   - This is the compliance backbone

4. UUIDs as primary keys
   - Allows external systems to reference our cases by UUID
   - Stable across environments (no auto-increment collisions)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, Column
from sqlmodel import Field, SQLModel

from app.schemas.enums import (
    CaseStatus,
    CaseType,
    DecisionAction,
    Jurisdiction,
)


# === Client (bank customer) ===

class ClientDB(SQLModel, table=True):
    """Persistent representation of a client."""
    
    __tablename__ = "clients"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Profile data stored as JSON (heterogeneous fields)
    full_name: str = Field(index=True)
    email: str | None = None
    nationality: str | None = None
    residence_country: str | None = None
    primary_jurisdiction: Jurisdiction = Field(index=True)
    
    risk_tolerance: str
    aum_chf: float
    esg_focus: bool = False
    is_pep: bool = Field(default=False, index=True)
    sanctions_check_passed: bool = True
    
    onboarded_at: date
    last_review_date: date | None = None
    
    # Flexible fields as JSON
    profile_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# === Case (item under review) ===

class CaseDB(SQLModel, table=True):
    """Persistent representation of a case under review."""
    
    __tablename__ = "cases"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    client_id: UUID = Field(foreign_key="clients.id", index=True)
    
    case_type: CaseType = Field(index=True)
    jurisdiction: Jurisdiction = Field(index=True)
    status: CaseStatus = Field(default=CaseStatus.PENDING, index=True)
    
    # Human-readable summary (denormalized for fast list queries)
    summary: str
    
    # Full context payload (varies per case_type)
    context_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    
    # ML scoring results (filled after scoring runs)
    risk_score: float | None = Field(default=None, index=True)
    risk_level: str | None = Field(default=None, index=True)
    confidence: float | None = None
    
    # Assignment
    assigned_to: str | None = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    scored_at: datetime | None = None
    resolved_at: datetime | None = None


# === Decision (compliance officer action) ===

class DecisionDB(SQLModel, table=True):
    """
    A compliance officer's decision — on a case or a drift customer.

    Exactly one of case_id / customer_id is set (enforced by DB CHECK constraint
    and Pydantic validator on DecisionCreate).

    Append-only: once recorded, never updated.
    If the officer changes their mind — a new decision record is created.

    NOTE: case_id is nullable as of the drift-engine workflow addition.
    Existing SQLite databases created before this change must be recreated
    (drop the file and let create_all rebuild) or migrated with:
        ALTER TABLE decisions ADD COLUMN customer_id TEXT;
        -- case_id NOT NULL constraint cannot be relaxed in SQLite without
        -- recreating the table; use a migration tool (Alembic) for production.
    """

    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "(case_id IS NULL) != (customer_id IS NULL)",
            name="ck_decision_exactly_one_id",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    case_id: UUID | None = Field(default=None, foreign_key="cases.id", index=True)
    customer_id: str | None = Field(default=None, index=True)  # drift-engine customer
    
    action: DecisionAction
    
    # Who made the decision (for now: free-text user identifier)
    officer_id: str = Field(index=True)
    
    # Justification (required for overrides of AI recommendation)
    rationale: str | None = None
    
    # Was this overriding the AI's recommendation?
    overrode_ai: bool = False
    ai_recommended_action: DecisionAction | None = None
    
    # Snapshot of AI state at decision time
    ai_risk_score: float | None = None
    ai_risk_level: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# === Audit Log (the compliance backbone) ===

class AuditEntryDB(SQLModel, table=True):
    """
    Immutable audit log entry.
    
    Every meaningful event is recorded here:
    - case_created
    - case_scored
    - explanation_generated
    - decision_recorded
    - jurisdiction_compared
    - data_exported
    
    APPEND-ONLY. Never UPDATE, never DELETE.
    This is the compliance backbone — if FINMA asks for audit trail,
    this is what we hand them.
    """
    
    __tablename__ = "audit_log"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # What happened
    event_type: str = Field(index=True)
    
    # What it relates to
    case_id: UUID | None = Field(default=None, index=True)
    client_id: UUID | None = Field(default=None, index=True)
    
    # Who did it (None if system event)
    actor_id: str | None = Field(default=None, index=True)
    actor_type: str = "system"  # "system" | "compliance_officer" | "rm" | "client"
    
    # Full payload (event-specific JSON)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    
    # Optional structured fields commonly used for filtering
    risk_score: float | None = Field(default=None, index=True)
    risk_level: str | None = Field(default=None, index=True)
    
    # When it happened
    occurred_at: datetime = Field(
        default_factory=datetime.utcnow, index=True
    )
