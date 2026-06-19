"""
Counterfactuals API — async DB version.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.counterfactual import CounterfactualResponse
from app.services.counterfactual import CounterfactualService

logger = get_logger(__name__)

router = APIRouter(prefix="/counterfactuals", tags=["counterfactuals"])


@router.post("/{case_id}", response_model=CounterfactualResponse)
async def generate_counterfactuals(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    n_scenarios: int = Query(3, ge=1, le=5),
) -> CounterfactualResponse:
    """Generate counterfactual scenarios for a case."""
    service = CounterfactualService(session)
    
    try:
        return await service.generate(case_id, n_scenarios=n_scenarios)
    except ValueError as e:
        # Genuine "case not found" or similar — surface as 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        # DiCE can fail for various reasons (small training set, infeasible
        # constraints, numerical issues). Counterfactuals are nice-to-have —
        # the rest of the case review still works without them. Return an
        # empty result with a note rather than crashing the whole panel.
        logger.exception("counterfactuals_failed", case_id=str(case_id))
        return CounterfactualResponse(
            case_id=case_id,
            original_score=0.0,
            original_outcome="unknown",
            counterfactuals=[],
            notes=f"Counterfactual generation unavailable for this case: {type(e).__name__}",
        )
