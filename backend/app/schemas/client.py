"""
Client (bank customer) schemas.

Represents an institutional or HNW client across all use cases.
Same client structure works for AMINA, Julius Baer, and Ripple scenarios.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import IdentifiedModel
from app.schemas.enums import Jurisdiction


class ClientProfile(BaseModel):
    """
    Client demographic and risk profile.
    
    Fields chosen to be useful for:
    - AMINA: behavioral baseline (location, transaction patterns)
    - JB: investment recommendation (risk tolerance, ESG, holdings)
    - Ripple: counterparty risk (entity type, jurisdiction)
    """
    
    # === Identity (anonymized in production) ===
    full_name: str
    email: EmailStr | None = None
    
    # === Demographics ===
    date_of_birth: date | None = None
    nationality: str | None = Field(None, description="ISO 3166-1 alpha-2")
    residence_country: str | None = Field(None, description="ISO 3166-1 alpha-2")
    
    # === Banking ===
    primary_jurisdiction: Jurisdiction
    onboarded_at: date
    
    # === Risk profile ===
    risk_tolerance: Literal["conservative", "moderate", "balanced", "growth", "aggressive"]
    aum_chf: float = Field(..., description="Assets under management in CHF", ge=0)
    
    # === Investment preferences ===
    esg_focus: bool = False
    preferred_asset_classes: list[str] = Field(default_factory=list)
    
    # === Compliance ===
    is_pep: bool = Field(False, description="Politically Exposed Person")
    sanctions_check_passed: bool = True
    last_review_date: date | None = None
    
    # === Behavioral metadata (for AMINA fraud detection) ===
    typical_transaction_hours: list[int] = Field(
        default_factory=lambda: list(range(8, 19)),
        description="Hours of day client typically active (0-23)",
    )
    typical_transaction_currency: str = "CHF"
    whitelist_wallets: list[str] = Field(
        default_factory=list,
        description="Pre-approved counterparty wallet addresses",
    )


class Client(IdentifiedModel):
    """Full client entity with ID and timestamps."""
    
    profile: ClientProfile


class ClientCreate(BaseModel):
    """Schema for creating a new client (input)."""
    
    profile: ClientProfile


class ClientRead(BaseModel):
    """Schema for returning client data (output)."""
    
    id: str
    profile: ClientProfile
    created_at: str
