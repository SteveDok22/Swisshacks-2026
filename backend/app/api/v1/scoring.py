"""
Scoring API — trigger ML scoring on cases.

Endpoints:
- POST /scoring/{case_id}      Score a specific case
- GET  /scoring/models         List available models
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.logging import get_logger
from app.ml.registry import ModelRegistry, get_registry
from app.schemas.scoring import ScoringResponse
from app.services.risk_engine import RiskEngine, get_risk_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/{case_id}", response_model=ScoringResponse)
async def score_case(
    case_id: UUID,
    engine: Annotated[RiskEngine, Depends(get_risk_engine)],
) -> ScoringResponse:
    """
    Run ML scoring on a case.
    
    Returns:
    - Risk score (0-100)
    - Risk level (low/medium/high/critical)
    - Confidence
    - Recommended action
    - Top features with SHAP contributions
    """
    try:
        result = engine.score_case(case_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("scoring_failed", case_id=str(case_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {e}",
        ) from e
    
    return ScoringResponse(case_id=case_id, result=result)


@router.get("/models", response_model=dict)
async def list_models(
    registry: Annotated[ModelRegistry, Depends(get_registry)],
) -> dict:
    """List all loaded ML models."""
    return {
        "loaded_count": len(registry.loaded_case_types),
        "case_types": [ct.value for ct in registry.loaded_case_types],
    }
