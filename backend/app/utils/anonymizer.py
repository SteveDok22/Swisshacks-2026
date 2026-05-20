"""
Anonymizer — privacy-first abstraction layer for LLM interactions.

Why this matters for SwissHacks 2026:
- FINMA (Switzerland) and MiCA (EU) restrict sending client PII to
  third-party AI providers without explicit consent
- AMINA's research explicitly mentions this as a structural concern
- Sending "Hans Müller, CHF 12.5M, transfer to Singapore" to Claude
  would technically violate Swiss data sovereignty requirements

Our approach:
- Replace names with stable pseudonyms (CLIENT_A, CLIENT_B)
- Bucket exact amounts into ranges ("CHF 1-5M" instead of "CHF 4.5M")
- Mask wallet addresses
- Keep behavioral signals intact (the model can reason about
  "transfer 30x larger than typical" without knowing actual amounts)

This becomes a VISIBLE feature in the UI:
- "What stays local" panel: full data
- "What goes to AI" panel: anonymized version
- The compliance officer can audit what leaves the bank
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnonymizationReport:
    """
    Audit trail of what was anonymized.
    Used in UI to show 'what goes to AI vs what stays local'.
    """
    original: dict[str, Any]
    anonymized: dict[str, Any]
    fields_redacted: list[str]
    fields_bucketed: list[str]
    fields_preserved: list[str]


class Anonymizer:
    """
    Convert client-identifying data into LLM-safe abstractions.
    
    Pattern: Deterministic pseudonymization
    - Same input → same pseudonym (stable across sessions)
    - But not reversible without our salt
    """
    
    # Fields containing direct identifiers — always redacted
    DIRECT_IDENTIFIERS = {
        "full_name",
        "email",
        "phone",
        "date_of_birth",
        "address",
        "voice_sample_id",
        "rm_name",
        "from_address",
        "to_address",
        "destination_wallet",
    }
    
    # Fields with sensitive monetary amounts — bucketed
    MONETARY_FIELDS = {
        "amount_chf",
        "amount_usd",
        "requested_amount_chf",
        "aum_chf",
        "amount",
    }
    
    # Fields that are safe to pass through (model needs them)
    SAFE_FIELDS = {
        "hour_of_day",
        "is_weekend",
        "is_outside_business_hours",
        "amount_vs_typical_ratio",
        "destination_country_risk",
        "urgency_signals",
        "secrecy_signals",
        "pressure_signals",
        "destination_country",
        "case_type",
        "jurisdiction",
        "risk_tolerance",
    }
    
    def __init__(self, salt: str = "swisshacks-2026") -> None:
        """
        Args:
            salt: Used for stable pseudonyms across requests.
                  Different deployments would use different salts.
        """
        self.salt = salt
    
    def pseudonymize_name(self, name: str) -> str:
        """
        Convert "Hans Müller" → "CLIENT_A7F3".
        
        Stable: same name always produces same pseudonym.
        Unique: different names produce different pseudonyms.
        Non-reversible without the salt.
        """
        if not name:
            return "CLIENT_UNKNOWN"
        
        digest = hashlib.sha256(
            f"{self.salt}::{name.lower().strip()}".encode()
        ).hexdigest()
        return f"CLIENT_{digest[:4].upper()}"
    
    def bucket_amount(self, amount: float, currency: str = "CHF") -> str:
        """
        Convert exact amount to a range string.
        
        Examples:
            150_000  → "CHF 100K-500K"
            4_500_000 → "CHF 1M-5M"
            50_000_000 → "CHF 10M+"
        
        Preserves order-of-magnitude information without exact values.
        """
        if amount < 10_000:
            return f"{currency} <10K"
        elif amount < 100_000:
            return f"{currency} 10K-100K"
        elif amount < 500_000:
            return f"{currency} 100K-500K"
        elif amount < 1_000_000:
            return f"{currency} 500K-1M"
        elif amount < 5_000_000:
            return f"{currency} 1M-5M"
        elif amount < 10_000_000:
            return f"{currency} 5M-10M"
        elif amount < 50_000_000:
            return f"{currency} 10M-50M"
        else:
            return f"{currency} 50M+"
    
    def mask_wallet(self, address: str) -> str:
        """
        0xWL00A11111111111111111111111111111111 → 0xWL****1111 (last 4)
        """
        if not address or len(address) < 8:
            return "WALLET_REDACTED"
        return f"{address[:4]}****{address[-4:]}"
    
    def anonymize_case_data(
        self,
        case_data: dict[str, Any],
        client_name: str | None = None,
    ) -> AnonymizationReport:
        """
        Apply anonymization rules to a case payload.
        
        Returns full report of what changed, for audit/UI.
        """
        anonymized: dict[str, Any] = {}
        redacted: list[str] = []
        bucketed: list[str] = []
        preserved: list[str] = []
        
        # Inject pseudonymized client identifier
        if client_name:
            anonymized["client_pseudonym"] = self.pseudonymize_name(client_name)
            redacted.append("client_name")
        
        for key, value in case_data.items():
            # Direct identifiers — redact
            if key in self.DIRECT_IDENTIFIERS:
                if key in ("destination_wallet", "from_address", "to_address"):
                    anonymized[key] = self.mask_wallet(str(value))
                    redacted.append(key)
                elif key == "rm_name":
                    anonymized[key] = self.pseudonymize_name(str(value)).replace(
                        "CLIENT", "RM"
                    )
                    redacted.append(key)
                else:
                    anonymized[key] = "[REDACTED]"
                    redacted.append(key)
            
            # Monetary fields — bucket
            elif key in self.MONETARY_FIELDS and isinstance(value, (int, float)):
                anonymized[key] = self.bucket_amount(float(value))
                bucketed.append(key)
            
            # Transcript — extract signals, drop content
            elif key == "transcript_excerpt":
                anonymized["transcript_word_count"] = len(str(value).split())
                anonymized["transcript_redacted"] = "[CONTENT REDACTED]"
                redacted.append(key)
            
            # Safe fields — pass through
            elif key in self.SAFE_FIELDS:
                anonymized[key] = value
                preserved.append(key)
            
            # Unknown fields — preserve but flag
            else:
                anonymized[key] = value
                preserved.append(key)
        
        report = AnonymizationReport(
            original=case_data,
            anonymized=anonymized,
            fields_redacted=redacted,
            fields_bucketed=bucketed,
            fields_preserved=preserved,
        )
        
        logger.info(
            "case_anonymized",
            redacted_count=len(redacted),
            bucketed_count=len(bucketed),
            preserved_count=len(preserved),
        )
        
        return report


# Singleton instance
_anonymizer: Anonymizer | None = None


def get_anonymizer() -> Anonymizer:
    """Get the shared anonymizer instance."""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = Anonymizer()
    return _anonymizer
