"""
Jurisdictions API.

GET  /jurisdictions                 — list loaded jurisdictions + rules
GET  /jurisdictions/{code}          — get specific jurisdiction rules
POST /jurisdictions/compare/{case_id} — show case scored under each jurisdiction
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.logging import get_logger
from app.schemas.enums import Jurisdiction
from app.schemas.jurisdiction import JurisdictionAdjustedScore, JurisdictionRules
from app.services.jurisdiction import (
    JurisdictionService,
    get_jurisdiction_service,
)
from app.services.risk_engine import RiskEngine, get_risk_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


@router.get("", response_model=list[JurisdictionRules])
async def list_jurisdictions(
    service: Annotated[JurisdictionService, Depends(get_jurisdiction_service)],
) -> list[JurisdictionRules]:
    """List all loaded jurisdictions with their full rule packs."""
    return [
        service.get_rules(j) for j in service.loaded_jurisdictions
    ]


@router.get("/{code}", response_model=JurisdictionRules)
async def get_jurisdiction(
    code: Jurisdiction,
    service: Annotated[JurisdictionService, Depends(get_jurisdiction_service)],
) -> JurisdictionRules:
    """Get full rules for one jurisdiction."""
    try:
        return service.get_rules(code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/compare/{case_id}",
    response_model=dict[str, JurisdictionAdjustedScore],
)
async def compare_jurisdictions(
    case_id: UUID,
    jurisdiction_service: Annotated[
        JurisdictionService, Depends(get_jurisdiction_service)
    ],
    risk_engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> dict[str, JurisdictionAdjustedScore]:
    """
    Show how a case would be scored under EACH jurisdiction.
    
    Demo killer feature for AMINA challenge:
    "Same case: FINMA blocks, SFC escalates, MiCA approves."
    
    This directly addresses AMINA's published cross-jurisdictional pain point.
    """
    # First: get the base ML score
    try:
        ml_result = risk_engine.score_case(case_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    
    # Then: apply each jurisdiction's rules
    return jurisdiction_service.compare_jurisdictions(
        case_id, ml_result.score
    )
