"""
Public API for schemas package.

Import from here in your code:
    from app.schemas import Case, CaseRead, Client, RiskLevel
"""

from app.schemas.audit import (
    AuditEntryRead,
    AuditQueryParams,
    DecisionCreate,
    DecisionRead,
)
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
from app.schemas.counterfactual import (
    Counterfactual,
    CounterfactualResponse,
    FeatureChange,
)
from app.schemas.enums import (
    CaseStatus,
    CaseType,
    DecisionAction,
    Jurisdiction,
    RiskLevel,
)
from app.schemas.explanation import (
    AnonymizationPreview,
    CaseExplanation,
    ExplanationMetadata,
    ExplanationStreamChunk,
)
from app.schemas.jurisdiction import (
    ActionThresholds,
    CDDConfig,
    JurisdictionAdjustedScore,
    JurisdictionRules,
    ReportingConfig,
    TravelRuleConfig,
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
    # Counterfactuals
    "Counterfactual",
    "CounterfactualResponse",
    "FeatureChange",
    # Explanations
    "AnonymizationPreview",
    "CaseExplanation",
    "ExplanationMetadata",
    "ExplanationStreamChunk",
    # Jurisdiction
    "ActionThresholds",
    "CDDConfig",
    "JurisdictionAdjustedScore",
    "JurisdictionRules",
    "ReportingConfig",
    "TravelRuleConfig",
]
