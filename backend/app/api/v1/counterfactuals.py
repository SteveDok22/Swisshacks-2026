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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("counterfactuals_failed", case_id=str(case_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Counterfactual generation failed: {e}",
        ) from e
