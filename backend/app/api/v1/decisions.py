"""
Decisions API — compliance officer actions on cases.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.audit import DecisionCreate, DecisionRead
from app.services.decision import DecisionService

logger = get_logger(__name__)

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.post("", response_model=DecisionRead, status_code=status.HTTP_201_CREATED)
async def record_decision(
    payload: DecisionCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DecisionRead:
    """
    Record a compliance officer's decision on a case.
    
    If the decision overrides the AI's recommendation, `rationale` is REQUIRED.
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
    """Get all decisions ever made on a case."""
    service = DecisionService(session)
    decisions = await service.list_decisions_for_case(case_id)
    
    return [
        DecisionRead(
            id=d.id,
            case_id=d.case_id,
            action=d.action,
            officer_id=d.officer_id,
            rationale=d.rationale,
            overrode_ai=d.overrode_ai,
            ai_recommended_action=d.ai_recommended_action,
            ai_risk_score=d.ai_risk_score,
            ai_risk_level=d.ai_risk_level,
            created_at=d.created_at,
        )
        for d in decisions
    ]
