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

from datetime import UTC, datetime
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
        - Drift workflow (drift_id set): validates the customer against the
          live drift engine and captures its server-derived analysis state.
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
            analysis_snapshot={
                "source": "case",
                "confidence": case.confidence,
                "case_type": case.case_type.value,
                "jurisdiction": case.jurisdiction.value,
            },
            created_at=datetime.now(UTC),
        )
        self.session.add(decision)

        if payload.action in (DecisionAction.ALLOW, DecisionAction.BLOCK):
            case.status = CaseStatus.RESOLVED
            case.resolved_at = datetime.now(UTC)
        elif payload.action in (
            DecisionAction.STEP_UP_VERIFICATION,
            DecisionAction.ESCALATE,
        ):
            case.status = CaseStatus.IN_REVIEW

        case.updated_at = datetime.now(UTC)
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
            drift_id=decision.drift_id,
            action=decision.action,
            officer_id=decision.officer_id,
            rationale=decision.rationale,
            overrode_ai=decision.overrode_ai,
            ai_recommended_action=decision.ai_recommended_action,
            ai_risk_score=decision.ai_risk_score,
            ai_risk_level=decision.ai_risk_level,
            analysis_snapshot=decision.analysis_snapshot,
            created_at=decision.created_at,
        )

    async def _record_drift_decision(self, payload: DecisionCreate) -> DecisionRead:
        """Drift path — validate the subject and snapshot server analysis."""
        from app.drift.service import DRIFT_ANALYSIS_VERSION, get_drift_engine

        drift_id = payload.drift_id
        assert drift_id is not None

        detail = get_drift_engine().get_subject(drift_id)
        if detail is None:
            raise ValueError(f"Drift subject {drift_id!r} not found")

        ai_recommended = detail.recommended_action
        overrode_ai = ai_recommended != payload.action

        if overrode_ai and not payload.rationale:
            raise ValueError(
                "Rationale is required when overriding AI recommendation"
            )

        snapshot = {
            "analysis_version": DRIFT_ANALYSIS_VERSION,
            "drift_name": detail.name,
            "drift_score": detail.drift_score,
            "risk_level": detail.risk_level,
            "reached_tier": detail.reached_tier,
            "drift_velocity": detail.drift_velocity,
            "velocity_band": detail.velocity_band,
            "public_risk": detail.public_risk,
            "internal_risk": detail.internal_risk,
            "confirmation_lift": detail.confirmation_lift,
            "causal_label": detail.causal.label if detail.causal else None,
            "causal_p_risk": detail.causal.p_risk if detail.causal else None,
            "is_suspicious": (
                detail.stability.is_suspicious if detail.stability else None
            ),
            "recommended_action": ai_recommended.value,
        }

        decision = DecisionDB(
            drift_id=drift_id,
            action=payload.action,
            officer_id=payload.officer_id,
            rationale=payload.rationale,
            overrode_ai=overrode_ai,
            ai_recommended_action=ai_recommended,
            ai_risk_score=detail.drift_score,
            ai_risk_level=detail.risk_level,
            analysis_snapshot=snapshot,
            created_at=datetime.now(UTC),
        )
        self.session.add(decision)

        await self.session.flush()

        await self.audit.log(
            event_type="drift_decision_recorded",
            drift_id=drift_id,
            actor_id=payload.officer_id,
            actor_type="compliance_officer",
            risk_score=detail.drift_score,
            risk_level=detail.risk_level,
            payload={
                "drift_id": drift_id,
                "action": payload.action.value,
                "overrode_ai": overrode_ai,
                "ai_recommended_action": ai_recommended.value,
                "rationale": payload.rationale,
                "decision_id": str(decision.id),
                "analysis_snapshot": snapshot,
            },
        )

        logger.info(
            "drift_decision_recorded",
            drift_id=drift_id,
            action=payload.action.value,
            overrode_ai=overrode_ai,
            officer_id=payload.officer_id,
        )

        return DecisionRead(
            id=decision.id,
            case_id=decision.case_id,
            drift_id=decision.drift_id,
            action=decision.action,
            officer_id=decision.officer_id,
            rationale=decision.rationale,
            overrode_ai=decision.overrode_ai,
            ai_recommended_action=decision.ai_recommended_action,
            ai_risk_score=decision.ai_risk_score,
            ai_risk_level=decision.ai_risk_level,
            analysis_snapshot=decision.analysis_snapshot,
            created_at=decision.created_at,
        )
    
    async def list_decisions_for_subject(
        self, drift_id: str
    ) -> list[DecisionDB]:
        """Get all drift-engine decisions for a subject (chronological)."""
        statement = (
            select(DecisionDB)
            .where(DecisionDB.drift_id == drift_id)
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
