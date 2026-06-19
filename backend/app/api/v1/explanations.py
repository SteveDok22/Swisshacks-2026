"""
Explanations API — natural language explanations for cases.

Endpoints:
- POST /explanations/{case_id}              — full explanation (non-streaming)
- GET  /explanations/{case_id}/stream       — SSE streaming summary
- GET  /explanations/{case_id}/anonymization — show what goes to AI

The streaming endpoint is the "wow moment" for demo:
words appear progressively as Claude generates them.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.core.logging import get_logger
from app.schemas.explanation import AnonymizationPreview, CaseExplanation
from app.services.explanation import (
    ExplanationService,
    get_explanation_service,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/explanations", tags=["explanations"])


@router.post("/{case_id}", response_model=CaseExplanation)
async def generate_explanation(
    case_id: UUID,
    service: Annotated[
        ExplanationService, Depends(get_explanation_service)
    ],
) -> CaseExplanation:
    """
    Generate full natural language explanation for a case.
    
    Returns:
    - Executive summary (TL;DR for compliance officer)
    - Risk factors walkthrough
    - Alternative outcomes (counterfactuals, if high-risk)
    - Recommended action rationale
    - Jurisdiction notes
    
    All client data is anonymized before being sent to Claude.
    Metadata indicates anonymization stats and whether response was cached.
    
    Mock mode: If ANTHROPIC_API_KEY is not set, returns realistic
    placeholder responses (useful for development without burning tokens).
    """
    try:
        return service.generate(case_id)
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
    service: Annotated[
        ExplanationService, Depends(get_explanation_service)
    ],
) -> EventSourceResponse:
    """
    Stream natural language summary via Server-Sent Events.
    
    Each event is a `data:` line containing a text chunk.
    Final event has `event: done`.
    
    Frontend consumes via EventSource:
    
        const source = new EventSource('/api/v1/explanations/CASE_ID/stream');
        source.onmessage = (e) => display.textContent += e.data;
    """
    async def event_generator():
        try:
            async for chunk in service.stream_summary(case_id):
                # Yield chunks as SSE data events
                yield {
                    "event": "message",
                    "data": chunk,
                }
            # Signal completion
            yield {
                "event": "done",
                "data": "",
            }
        except ValueError as e:
            yield {
                "event": "error",
                "data": str(e),
            }
        except Exception as e:
            logger.exception("stream_error", case_id=str(case_id))
            yield {
                "event": "error",
                "data": str(e),
            }
    
    return EventSourceResponse(event_generator())


@router.get(
    "/{case_id}/anonymization",
    response_model=AnonymizationPreview,
)
async def get_anonymization_preview(
    case_id: UUID,
    service: Annotated[
        ExplanationService, Depends(get_explanation_service)
    ],
) -> AnonymizationPreview:
    """
    Show what data is sent to the LLM vs what stays local.
    
    This powers the "Privacy" panel in the UI — a visible
    demonstration of FINMA-compliant data handling.
    
    The compliance officer can audit exactly what leaves the bank
    before approving the use of AI for their workflow.
    """
    try:
        return service.get_anonymization_preview(case_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
