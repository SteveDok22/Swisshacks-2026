"""
Decisions API — compliance officer actions on cases and drift customers.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import DecisionDB
from app.db.session import get_session
from app.drift.service import get_drift_engine
from app.schemas.audit import DecisionCreate, DecisionRead
from app.services.decision import DecisionService

logger = get_logger(__name__)

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _to_read(d: DecisionDB) -> DecisionRead:
    return DecisionRead(
        id=d.id,
        case_id=d.case_id,
        customer_id=d.customer_id,
        action=d.action,
        officer_id=d.officer_id,
        rationale=d.rationale,
        overrode_ai=d.overrode_ai,
        ai_recommended_action=d.ai_recommended_action,
        ai_risk_score=d.ai_risk_score,
        ai_risk_level=d.ai_risk_level,
        analysis_snapshot=d.analysis_snapshot,
        created_at=d.created_at,
    )


@router.post("", response_model=DecisionRead, status_code=status.HTTP_201_CREATED)
async def record_decision(
    payload: DecisionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DecisionRead:
    """
    Record a compliance officer's decision.

    Accepts either ``case_id`` (case-review workflow) or ``customer_id``
    (drift-engine workflow) — not both, and at least one is required.

    If the decision overrides the AI's recommendation, ``rationale`` is REQUIRED.
    """
    service = DecisionService(session)

    try:
        return await service.record_decision(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.get("/case/{case_id}", response_model=list[DecisionRead])
async def list_case_decisions(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DecisionRead]:
    """Get all decisions ever made on a case (chronological).

    Returns an empty list when the case exists but has no decisions, or when
    the case_id is unknown — callers should not infer case existence from this.
    """
    service = DecisionService(session)
    decisions = await service.list_decisions_for_case(case_id)
    return [_to_read(d) for d in decisions]


@router.get("/customer/{customer_id}", response_model=list[DecisionRead])
async def list_customer_decisions(
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DecisionRead]:
    """Get all drift-engine decisions ever made on a customer (chronological).

    Returns an empty list when the customer exists but has no decisions.
    """
    if get_drift_engine().get_customer(customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
        )
    service = DecisionService(session)
    decisions = await service.list_decisions_for_customer(customer_id)
    return [_to_read(d) for d in decisions]
