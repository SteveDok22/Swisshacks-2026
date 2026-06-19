"""
Cases API — the central resource of the platform.

Endpoints:
- GET    /cases                    List cases (filterable)
- GET    /cases/{case_id}          Get single case (full detail)
- POST   /cases                    Create a new case
- PATCH  /cases/{case_id}/status   Update case status
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.logging import get_logger
from app.schemas.case import (
    Case,
    CaseContext,
    CaseCreate,
    CaseListItem,
    CaseRead,
)
from app.schemas.common import PaginatedResponse
from app.schemas.enums import CaseStatus, CaseType, Jurisdiction
from app.services.store import InMemoryStore, get_store

logger = get_logger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=PaginatedResponse)
async def list_cases(
    store: Annotated[InMemoryStore, Depends(get_store)],
    case_type: CaseType | None = Query(None, description="Filter by case type"),
    status_filter: CaseStatus | None = Query(None, alias="status"),
    jurisdiction: Jurisdiction | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    """
    List cases with optional filtering.
    
    Returns compact CaseListItem objects suitable for list views.
    Use GET /cases/{id} for full detail.
    """
    offset = (page - 1) * page_size
    
    cases, total = store.list_cases(
        case_type=case_type.value if case_type else None,
        status=status_filter.value if status_filter else None,
        jurisdiction=jurisdiction.value if jurisdiction else None,
        limit=page_size,
        offset=offset,
    )
    
    items = [
        CaseListItem(
            id=c.id,
            case_type=c.case_type,
            jurisdiction=c.jurisdiction,
            status=c.status,
            summary=c.context.summary,
            risk_score=c.risk_score,
            risk_level=c.risk_level,
            created_at=c.created_at,
        )
        for c in cases
    ]
    
    logger.info(
        "cases_listed",
        count=len(items),
        total=total,
        filters={
            "case_type": case_type,
            "status": status_filter,
            "jurisdiction": jurisdiction,
        },
    )
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: UUID,
    store: Annotated[InMemoryStore, Depends(get_store)],
) -> CaseRead:
    """Get a single case by ID with full context."""
    
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    
    return CaseRead(
        id=case.id,
        client_id=case.client_id,
        case_type=case.case_type,
        jurisdiction=case.jurisdiction,
        status=case.status,
        context=case.context,
        risk_score=case.risk_score,
        risk_level=case.risk_level,
        confidence=case.confidence,
        assigned_to=case.assigned_to,
        created_at=case.created_at,
        scored_at=case.scored_at,
        resolved_at=case.resolved_at,
    )


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    store: Annotated[InMemoryStore, Depends(get_store)],
) -> CaseRead:
    """
    Create a new case.
    
    Note: This does NOT trigger scoring automatically.
    Call POST /scoring/{case_id} after creation (or use POST /scoring/score-now).
    """
    
    # Validate client exists
    if store.get_client(payload.client_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Client {payload.client_id} does not exist",
        )
    
    case = Case(
        client_id=payload.client_id,
        case_type=payload.case_type,
        jurisdiction=payload.jurisdiction,
        context=payload.context,
        status=CaseStatus.PENDING,
    )
    
    store.add_case(case)
    
    logger.info(
        "case_created",
        case_id=str(case.id),
        case_type=case.case_type,
        jurisdiction=case.jurisdiction,
        client_id=str(case.client_id),
    )
    
    return CaseRead(
        id=case.id,
        client_id=case.client_id,
        case_type=case.case_type,
        jurisdiction=case.jurisdiction,
        status=case.status,
        context=case.context,
        risk_score=case.risk_score,
        risk_level=case.risk_level,
        confidence=case.confidence,
        assigned_to=case.assigned_to,
        created_at=case.created_at,
        scored_at=case.scored_at,
        resolved_at=case.resolved_at,
    )


@router.patch("/{case_id}/status", response_model=CaseRead)
async def update_case_status(
    case_id: UUID,
    new_status: CaseStatus,
    store: Annotated[InMemoryStore, Depends(get_store)],
) -> CaseRead:
    """Update a case's workflow status."""
    
    updated = store.update_case(case_id, status=new_status)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    
    logger.info(
        "case_status_updated",
        case_id=str(case_id),
        new_status=new_status,
    )
    
    return CaseRead(
        id=updated.id,
        client_id=updated.client_id,
        case_type=updated.case_type,
        jurisdiction=updated.jurisdiction,
        status=updated.status,
        context=updated.context,
        risk_score=updated.risk_score,
        risk_level=updated.risk_level,
        confidence=updated.confidence,
        assigned_to=updated.assigned_to,
        created_at=updated.created_at,
        scored_at=updated.scored_at,
        resolved_at=updated.resolved_at,
    )
