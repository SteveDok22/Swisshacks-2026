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
        
        # Get model (with fallback for unsupported case types)
        model = self.registry.get_or_raise(case.case_type)
        
        # Score
        result = model.score(case, client_context)
        
        # === Rule-based amplification for known critical flags ===
        # When the ML model is a fallback baseline (e.g., social_engineering
        # model scoring an XRPL transaction), it may miss case-specific red
        # flags. We apply deterministic rule overrides here so well-known
        # critical signals are never silently dismissed.
        result = self._apply_critical_overrides(case, result)
        
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
    
    def _apply_critical_overrides(self, case, result: RiskScoreResult) -> RiskScoreResult:
        """
        Apply deterministic rule overrides for known critical signals.
        
        The ML model may not catch every red flag (especially when used as a
        fallback baseline for case types it wasn't trained on). These rules
        guarantee specific high-severity signals always trigger appropriate
        scores, regardless of model output.
        
        Order: rules MAY raise the score, never lower it.
        """
        from app.schemas.enums import DecisionAction, RiskLevel
        
        data = case.context.data
        score = result.score
        
        # === Sanctions match: always critical ===
        if data.get("sanctions_match") is True:
            score = max(score, 95.0)
        
        # === Mixer proximity 1-2 hops: high-risk ===
        mixer_hops = data.get("mixer_proximity_hops")
        if isinstance(mixer_hops, int) and 1 <= mixer_hops <= 2:
            score = max(score, 75.0)
        elif isinstance(mixer_hops, int) and mixer_hops == 3:
            score = max(score, 55.0)
        
        # === PEP + new counterparty + large amount: amplify ===
        client_is_pep = (
            result.top_features
            and any(
                f.name == "is_pep" and f.value
                for f in result.top_features
            )
        )
        if client_is_pep and not data.get("counterparty_whitelisted", False):
            amount = float(
                data.get("requested_amount_chf")
                or data.get("amount")
                or 0
            )
            if amount > 1_000_000:
                score = max(score, 80.0)
        
        # No change? Return original
        if score == result.score:
            return result
        
        # Derive new level + action from boosted score
        if score >= 86:
            level = RiskLevel.CRITICAL
            action = DecisionAction.BLOCK
        elif score >= 61:
            level = RiskLevel.HIGH
            action = DecisionAction.ESCALATE
        elif score >= 31:
            level = RiskLevel.MEDIUM
            action = DecisionAction.STEP_UP_VERIFICATION
        else:
            level = RiskLevel.LOW
            action = DecisionAction.ALLOW
        
        logger.info(
            "rule_override_applied",
            original_score=result.score,
            new_score=score,
            case_id=str(case.id),
        )
        
        return RiskScoreResult(
            score=score,
            level=level,
            confidence=result.confidence,
            recommended_action=action,
            top_features=result.top_features,
            model_name=result.model_name,
            model_version=result.model_version,
            scored_at=result.scored_at,
        )
