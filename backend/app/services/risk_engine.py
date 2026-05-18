"""
Risk Engine — high-level service that orchestrates scoring.

Responsibilities:
1. Look up the case
2. Look up the client (for context features)
3. Get the right model from registry
4. Run scoring
5. Update the case with results
6. (Day 6) Log to audit trail

This is the LAYER OF BUSINESS LOGIC.
API endpoints just call this service — they don't know about models.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.logging import get_logger
from app.ml.registry import ModelRegistry, get_registry
from app.schemas.case import Case
from app.schemas.scoring import RiskScoreResult
from app.services.store import InMemoryStore, get_store

logger = get_logger(__name__)


class RiskEngine:
    """High-level scoring orchestrator."""
    
    def __init__(
        self,
        store: InMemoryStore | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.store = store or get_store()
        self.registry = registry or get_registry()
    
    def score_case(self, case_id: UUID) -> RiskScoreResult:
        """
        Run scoring for a case.
        
        Steps:
        1. Fetch case + client
        2. Build client context for feature extraction
        3. Get model from registry
        4. Run scoring
        5. Update case with results
        """
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        # Build client context
        client = self.store.get_client(case.client_id)
        client_context = self._build_client_context(client)
        
        # Get model
        model = self.registry.get_or_raise(case.case_type)
        
        # Score
        result = model.score(case, client_context)
        
        # Update case in store
        self.store.update_case(
            case_id,
            risk_score=result.score,
            risk_level=result.level.value,
            confidence=result.confidence,
            scored_at=datetime.utcnow(),
        )
        
        logger.info(
            "case_scored_via_engine",
            case_id=str(case_id),
            score=result.score,
            level=result.level.value,
        )
        
        return result
    
    def _build_client_context(self, client) -> dict:
        """
        Build client context for feature extraction.
        
        This bridges the Client schema with what feature extractors expect.
        Keeps feature extractors decoupled from Client model.
        """
        if client is None:
            return {}
        
        profile = client.profile
        
        # Days since last review
        days_since_review = 90
        if profile.last_review_date:
            days_since_review = (
                datetime.utcnow().date() - profile.last_review_date
            ).days
        
        # Typical transaction amount estimate (10% of AUM as heuristic)
        typical_amount = profile.aum_chf * 0.02  # 2% of AUM
        
        return {
            "aum_chf": profile.aum_chf,
            "is_pep": profile.is_pep,
            "typical_hours": profile.typical_transaction_hours,
            "typical_amount": typical_amount,
            "whitelist_wallets": profile.whitelist_wallets,
            "risk_tolerance": profile.risk_tolerance,
            "days_since_review": days_since_review,
        }


# === Dependency for FastAPI ===
def get_risk_engine() -> RiskEngine:
    """FastAPI dependency for injecting the risk engine."""
    return RiskEngine()
