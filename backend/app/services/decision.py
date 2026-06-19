"""
Decision Service — records compliance officer actions.

Critical for AMINA compliance demo:
- Officer reviews AI recommendation
- Officer accepts, modifies, or overrides
- Decision is logged immutably with full context
- If officer overrode AI → rationale is REQUIRED

This decoupling between AI recommendation and human decision
is exactly what regulators (FINMA, MiCA) want to see.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.db.models import CaseDB, DecisionDB
from app.schemas.audit import DecisionCreate, DecisionRead
from app.schemas.enums import CaseStatus, DecisionAction
from app.services.audit import AuditService

logger = get_logger(__name__)


class DecisionService:
    """Records compliance officer decisions on cases."""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
    
    async def record_decision(self, payload: DecisionCreate) -> DecisionRead:
        """
        Record a compliance officer's decision.

        Two workflows are supported:
        - Case workflow (case_id set): looks up the case, captures AI state.
        - Drift workflow (customer_id set): uses caller-supplied ai_hint as
          the AI recommendation; no case record is required or modified.
        """
        if payload.case_id is not None:
            return await self._record_case_decision(payload)
        return await self._record_drift_decision(payload)

    async def _record_case_decision(self, payload: DecisionCreate) -> DecisionRead:
        """Case-review path — requires an existing case record."""
        case_stmt = select(CaseDB).where(CaseDB.id == payload.case_id)
        result = await self.session.execute(case_stmt)
        case = result.scalar_one_or_none()

        if case is None:
            raise ValueError(f"Case {payload.case_id} not found")

        ai_recommended = self._derive_ai_action(case)
        overrode_ai = (
            ai_recommended is not None and ai_recommended != payload.action
        )

        if overrode_ai and not payload.rationale:
            raise ValueError(
                "Rationale is required when overriding AI recommendation"
            )

        decision = DecisionDB(
            case_id=payload.case_id,
            action=payload.action,
            officer_id=payload.officer_id,
            rationale=payload.rationale,
            overrode_ai=overrode_ai,
            ai_recommended_action=ai_recommended,
            ai_risk_score=case.risk_score,
            ai_risk_level=case.risk_level,
            created_at=datetime.utcnow(),
        )
        self.session.add(decision)

        if payload.action in (DecisionAction.ALLOW, DecisionAction.BLOCK):
            case.status = CaseStatus.RESOLVED
            case.resolved_at = datetime.utcnow()
        elif payload.action in (
            DecisionAction.STEP_UP_VERIFICATION,
            DecisionAction.ESCALATE,
        ):
            case.status = CaseStatus.IN_REVIEW

        case.updated_at = datetime.utcnow()
        self.session.add(case)

        await self.session.flush()

        await self.audit.log(
            event_type="decision_recorded",
            case_id=payload.case_id,
            client_id=case.client_id,
            actor_id=payload.officer_id,
            actor_type="compliance_officer",
            risk_score=case.risk_score,
            risk_level=case.risk_level,
            payload={
                "action": payload.action.value,
                "overrode_ai": overrode_ai,
                "ai_recommended_action": (
                    ai_recommended.value if ai_recommended else None
                ),
                "rationale": payload.rationale,
                "decision_id": str(decision.id),
                "jurisdiction": str(case.jurisdiction),
            },
        )

        logger.info(
            "decision_recorded",
            case_id=str(payload.case_id),
            action=payload.action.value,
            overrode_ai=overrode_ai,
            officer_id=payload.officer_id,
        )

        return DecisionRead(
            id=decision.id,
            case_id=decision.case_id,
            customer_id=decision.customer_id,
            action=decision.action,
            officer_id=decision.officer_id,
            rationale=decision.rationale,
            overrode_ai=decision.overrode_ai,
            ai_recommended_action=decision.ai_recommended_action,
            ai_risk_score=decision.ai_risk_score,
            ai_risk_level=decision.ai_risk_level,
            created_at=decision.created_at,
        )

    async def _record_drift_decision(self, payload: DecisionCreate) -> DecisionRead:
        """Drift-engine path — no case record; uses ai_hint for override detection."""
        ai_recommended = payload.ai_hint
        overrode_ai = (
            ai_recommended is not None and ai_recommended != payload.action
        )

        if overrode_ai and not payload.rationale:
            raise ValueError(
                "Rationale is required when overriding AI recommendation"
            )

        decision = DecisionDB(
            customer_id=payload.customer_id,
            action=payload.action,
            officer_id=payload.officer_id,
            rationale=payload.rationale,
            overrode_ai=overrode_ai,
            ai_recommended_action=ai_recommended,
            created_at=datetime.utcnow(),
        )
        self.session.add(decision)

        await self.session.flush()

        await self.audit.log(
            event_type="drift_decision_recorded",
            actor_id=payload.officer_id,
            actor_type="compliance_officer",
            payload={
                "customer_id": payload.customer_id,
                "action": payload.action.value,
                "overrode_ai": overrode_ai,
                "ai_recommended_action": (
                    ai_recommended.value if ai_recommended else None
                ),
                "rationale": payload.rationale,
                "decision_id": str(decision.id),
            },
        )

        logger.info(
            "drift_decision_recorded",
            customer_id=payload.customer_id,
            action=payload.action.value,
            overrode_ai=overrode_ai,
            officer_id=payload.officer_id,
        )

        return DecisionRead(
            id=decision.id,
            case_id=None,
            customer_id=decision.customer_id,
            action=decision.action,
            officer_id=decision.officer_id,
            rationale=decision.rationale,
            overrode_ai=decision.overrode_ai,
            ai_recommended_action=decision.ai_recommended_action,
            ai_risk_score=None,
            ai_risk_level=None,
            created_at=decision.created_at,
        )
    
    async def list_decisions_for_customer(
        self, customer_id: str
    ) -> list[DecisionDB]:
        """Get all drift-engine decisions for a customer (chronological)."""
        statement = (
            select(DecisionDB)
            .where(DecisionDB.customer_id == customer_id)
            .order_by(DecisionDB.created_at)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_decisions_for_case(
        self, case_id: UUID
    ) -> list[DecisionDB]:
        """Get all decisions ever made on a case (chronological)."""
        statement = (
            select(DecisionDB)
            .where(DecisionDB.case_id == case_id)
            .order_by(DecisionDB.created_at)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
    
    def _derive_ai_action(self, case: CaseDB) -> DecisionAction | None:
        """
        Derive AI's recommended action from case risk score.
        
        Maps to same thresholds used in ML pipeline:
        - 0-30: ALLOW
        - 31-60: STEP_UP_VERIFICATION
        - 61-85: ESCALATE / BLOCK based on confidence
        - 86+: BLOCK
        """
        if case.risk_score is None:
            return None
        
        if case.risk_score < 31:
            return DecisionAction.ALLOW
        elif case.risk_score < 61:
            return DecisionAction.STEP_UP_VERIFICATION
        elif case.risk_score < 86:
            # ESCALATE if confidence low, BLOCK if high
            if case.confidence and case.confidence >= 0.85:
                return DecisionAction.BLOCK
            else:
                return DecisionAction.ESCALATE
        else:
            return DecisionAction.BLOCK
