"""
Public API for schemas package.

Import from here in your code:
    from app.schemas import Case, CaseRead, Client, RiskLevel
"""

from app.schemas.case import (
    Case,
    CaseBase,
    CaseContext,
    CaseCreate,
    CaseListItem,
    CaseRead,
)
from app.schemas.client import Client, ClientCreate, ClientProfile, ClientRead
from app.schemas.common import (
    ErrorResponse,
    IdentifiedModel,
    PaginatedResponse,
    TimestampedModel,
)
from app.schemas.enums import (
    CaseStatus,
    CaseType,
    DecisionAction,
    Jurisdiction,
    RiskLevel,
)
from app.schemas.scoring import (
    FeatureContribution,
    RiskScoreResult,
    ScoringRequest,
    ScoringResponse,
)

__all__ = [
    # Enums
    "CaseStatus",
    "CaseType",
    "DecisionAction",
    "Jurisdiction",
    "RiskLevel",
    # Common
    "ErrorResponse",
    "IdentifiedModel",
    "PaginatedResponse",
    "TimestampedModel",
    # Client
    "Client",
    "ClientCreate",
    "ClientProfile",
    "ClientRead",
    # Case
    "Case",
    "CaseBase",
    "CaseContext",
    "CaseCreate",
    "CaseListItem",
    "CaseRead",
    # Scoring
    "FeatureContribution",
    "RiskScoreResult",
    "ScoringRequest",
    "ScoringResponse",
]
