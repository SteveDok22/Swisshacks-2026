"""
Risk Engine — async version using DbStore.

Responsibilities:
1. Look up the case
2. Look up the client (for context features)
3. Get the right model from registry
4. Run scoring
5. Update the case with results
6. Log to audit trail
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ml.registry import ModelRegistry, get_registry
from app.schemas.scoring import RiskScoreResult
from app.services.audit import AuditService
from app.services.db_store import DbStore

logger = get_logger(__name__)


class RiskEngine:
    """High-level scoring orchestrator."""
    
    def __init__(
        self,
        session: AsyncSession,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.session = session
        self.store = DbStore(session)
        self.audit = AuditService(session)
        self.registry = registry or get_registry()
    
    async def score_case(self, case_id: UUID) -> RiskScoreResult:
        """Run scoring for a case."""
        case = await self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        # Build client context
        client = await self.store.get_client(case.client_id)
        client_context = self._build_client_context(client)
        
        # Get model
        model = self.registry.get_or_raise(case.case_type)
        
        # Score
        result = model.score(case, client_context)
        
        # Update case in DB
        await self.store.update_case(
            case_id,
            risk_score=result.score,
            risk_level=result.level.value,
            confidence=result.confidence,
            scored_at=datetime.utcnow(),
        )
        
        # Audit log
        await self.audit.log(
            event_type="case_scored",
            case_id=case_id,
            client_id=case.client_id,
            risk_score=result.score,
            risk_level=result.level.value,
            payload={
                "model": result.model_name,
                "model_version": result.model_version,
                "recommended_action": result.recommended_action.value,
                "confidence": result.confidence,
                "top_features": [
                    {"name": f.name, "contribution": f.contribution}
                    for f in result.top_features[:5]
                ],
            },
        )
        
        return result
    
    def _build_client_context(self, client) -> dict:
        """Build client context for feature extraction."""
        if client is None:
            return {}
        
        profile = client.profile
        
        days_since_review = 90
        if profile.last_review_date:
            days_since_review = (
                datetime.utcnow().date() - profile.last_review_date
            ).days
        
        typical_amount = profile.aum_chf * 0.02
        
        return {
            "aum_chf": profile.aum_chf,
            "is_pep": profile.is_pep,
            "typical_hours": profile.typical_transaction_hours,
            "typical_amount": typical_amount,
            "whitelist_wallets": profile.whitelist_wallets,
            "risk_tolerance": profile.risk_tolerance,
            "days_since_review": days_since_review,
        }
