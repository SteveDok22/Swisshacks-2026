"""
Jurisdictions API — async DB version.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.enums import Jurisdiction
from app.schemas.jurisdiction import JurisdictionAdjustedScore, JurisdictionRules
from app.services.audit import AuditService
from app.services.jurisdiction import JurisdictionService
from app.services.risk_engine import RiskEngine

logger = get_logger(__name__)

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


@router.get("", response_model=list[JurisdictionRules])
async def list_jurisdictions() -> list[JurisdictionRules]:
    """List all loaded jurisdictions."""
    service = JurisdictionService()
    return [service.get_rules(j) for j in service.loaded_jurisdictions]


@router.get("/{code}", response_model=JurisdictionRules)
async def get_jurisdiction(code: Jurisdiction) -> JurisdictionRules:
    """Get full rules for one jurisdiction."""
    service = JurisdictionService()
    try:
        return service.get_rules(code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.post(
    "/compare/{case_id}",
    response_model=dict[str, JurisdictionAdjustedScore],
)
async def compare_jurisdictions(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor_id: str | None = Query(None, description="ID of the officer running the comparison"),
) -> dict[str, JurisdictionAdjustedScore]:
    """Show how a case would be scored under EACH jurisdiction."""
    jurisdiction_service = JurisdictionService(session)
    risk_engine = RiskEngine(session)

    try:
        ml_result = await risk_engine.score_case(case_id, actor_id=actor_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    results = await jurisdiction_service.compare_jurisdictions(
        case_id, ml_result.score
    )

    await AuditService(session).log(
        event_type="jurisdiction_compared",
        case_id=case_id,
        actor_id=actor_id,
        actor_type="compliance_officer" if actor_id else "system",
        risk_score=ml_result.score,
        risk_level=ml_result.level.value,
        payload={
            "jurisdictions_compared": list(results.keys()),
            "base_score": ml_result.score,
            "adjusted_scores": {
                j: r.adjusted_score for j, r in results.items()
            },
        },
    )

    return results
