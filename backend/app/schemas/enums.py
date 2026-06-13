"""
Application-wide enums.

Why a separate file:
- Reused across schemas, services, ML
- Single source of truth (no magic strings)
- Type-safe with IDE autocomplete
"""

from enum import StrEnum


class Jurisdiction(StrEnum):
    """Regulatory jurisdictions we support."""
    
    CH = "CH"       # Switzerland (FINMA)
    EU = "EU"       # European Union (MiCA)
    HK = "HK"       # Hong Kong (SFC)
    AE = "AE"       # UAE / ADGM (FSRA)


class CaseType(StrEnum):
    """
    Types of cases we score.
    Each maps to a different feature engineering pipeline.
    """
    
    # AMINA use cases
    SOCIAL_ENGINEERING = "social_engineering"  # Voice + behavior fraud
    PORTFOLIO_RISK = "portfolio_risk"          # RWA portfolio monitoring
    
    # Julius Baer use cases
    INVESTMENT_RECOMMENDATION = "investment_recommendation"
    CLIENT_ONBOARDING = "client_onboarding"
    
    # Ripple use cases
    XRPL_TRANSACTION = "xrpl_transaction"      # AML scoring on-chain

    # AMINA Challenge 4 — Dynamic Risk Profiling
    KYC_DRIFT = "kyc_drift"                     # Slow structural risk drift


class RiskLevel(StrEnum):
    """
    Human-readable risk categorization.
    Maps to numeric score ranges (defined in services/risk_engine.py).
    """
    
    LOW = "low"            # 0-30
    MEDIUM = "medium"      # 31-60
    HIGH = "high"          # 61-85
    CRITICAL = "critical"  # 86-100


class DecisionAction(StrEnum):
    """Possible actions a compliance officer can take."""
    
    ALLOW = "allow"
    STEP_UP_VERIFICATION = "step_up_verification"
    ESCALATE = "escalate"
    BLOCK = "block"


class CaseStatus(StrEnum):
    """Workflow status of a case."""
    
    PENDING = "pending"            # Awaiting human review
    IN_REVIEW = "in_review"        # Officer is looking at it
    RESOLVED = "resolved"          # Decision made
    EXPIRED = "expired"            # Timed out without action
