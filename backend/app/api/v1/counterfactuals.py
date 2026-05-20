"""
Counterfactuals API.

POST /counterfactuals/{case_id}  — generate "what-if" scenarios
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.logging import get_logger
from app.schemas.counterfactual import CounterfactualResponse
from app.services.counterfactual import (
    CounterfactualService,
    get_counterfactual_service,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/counterfactuals", tags=["counterfactuals"])


@router.post("/{case_id}", response_model=CounterfactualResponse)
async def generate_counterfactuals(
    case_id: UUID,
    service: Annotated[
        CounterfactualService,
        Depends(get_counterfactual_service),
    ],
    n_scenarios: int = Query(
        3,
        ge=1,
        le=5,
        description="Number of counterfactual scenarios to generate",
    ),
) -> CounterfactualResponse:
    """
    Generate counterfactual scenarios for a case.
    
    Answers: "What minimal changes would flip this to a low-risk case?"
    
    Useful for:
    - Escalation discussions ("Could this be approved if X?")
    - Audit trail (showing alternative decisions considered)
    - Model interpretability beyond SHAP
    
    Note: Only meaningful for HIGH-RISK cases. Low-risk cases return empty list.
    """
    try:
        result = service.generate(case_id, n_scenarios=n_scenarios)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("counterfactuals_failed", case_id=str(case_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Counterfactual generation failed: {e}",
        ) from e
    
    return result
