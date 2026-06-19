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
from app.services.audit import AuditService
from app.services.counterfactual import CounterfactualService

logger = get_logger(__name__)

router = APIRouter(prefix="/counterfactuals", tags=["counterfactuals"])


@router.post("/{case_id}", response_model=CounterfactualResponse)
async def generate_counterfactuals(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    n_scenarios: int = Query(3, ge=1, le=5),
    actor_id: str | None = Query(None, description="ID of the officer requesting counterfactuals"),
) -> CounterfactualResponse:
    """Generate counterfactual scenarios for a case."""
    service = CounterfactualService(session)

    try:
        result = await service.generate(case_id, n_scenarios=n_scenarios)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("counterfactuals_failed", case_id=str(case_id))
        result = CounterfactualResponse(
            case_id=case_id,
            original_score=0.0,
            original_outcome="unknown",
            counterfactuals=[],
            notes=f"Counterfactual generation unavailable for this case: {type(e).__name__}",
        )

    await AuditService(session).log(
        event_type="counterfactuals_generated",
        case_id=case_id,
        actor_id=actor_id,
        actor_type="compliance_officer" if actor_id else "system",
        payload={
            "n_scenarios_requested": n_scenarios,
            "scenarios_generated": len(result.counterfactuals),
            "notes": result.notes,
        },
    )

    return result
