"""
Explanations API — async DB version.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.explanation import AnonymizationPreview, CaseExplanation
from app.services.explanation import ExplanationService

logger = get_logger(__name__)

router = APIRouter(prefix="/explanations", tags=["explanations"])


@router.post("/{case_id}", response_model=CaseExplanation)
async def generate_explanation(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseExplanation:
    """Generate full natural language explanation."""
    service = ExplanationService(session)
    
    try:
        return await service.generate(case_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("explanation_generation_failed", case_id=str(case_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Explanation failed: {e}",
        ) from e


@router.get("/{case_id}/stream")
async def stream_explanation(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EventSourceResponse:
    """Stream natural language summary via SSE."""
    service = ExplanationService(session)
    
    async def event_generator():
        try:
            async for chunk in service.stream_summary(case_id):
                yield {"event": "message", "data": chunk}
            yield {"event": "done", "data": ""}
        except ValueError as e:
            yield {"event": "error", "data": str(e)}
        except Exception as e:
            logger.exception("stream_error", case_id=str(case_id))
            yield {"event": "error", "data": str(e)}
    
    return EventSourceResponse(event_generator())


@router.get(
    "/{case_id}/anonymization",
    response_model=AnonymizationPreview,
)
async def get_anonymization_preview(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnonymizationPreview:
    """Show what data is sent to LLM vs what stays local."""
    service = ExplanationService(session)
    
    try:
        return await service.get_anonymization_preview(case_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
