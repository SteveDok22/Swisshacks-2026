"""
Cases API — async DB version.

Endpoints:
- GET    /cases                    List cases (filterable)
- GET    /cases/{case_id}          Get single case (full detail)
- POST   /cases                    Create a new case
- PATCH  /cases/{case_id}/status   Update case status
- GET    /cases/{case_id}/history  Audit trail for this case
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.audit import AuditEntryRead
from app.schemas.case import (
    Case,
    CaseCreate,
    CaseListItem,
    CaseRead,
)
from app.schemas.common import PaginatedResponse
from app.schemas.enums import CaseStatus, CaseType, Jurisdiction
from app.services.audit import AuditService
from app.services.db_store import DbStore

logger = get_logger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=PaginatedResponse)
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
    case_type: CaseType | None = Query(None),
    status_filter: CaseStatus | None = Query(None, alias="status"),
    jurisdiction: Jurisdiction | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    """List cases with optional filtering."""
    store = DbStore(session)
    offset = (page - 1) * page_size

    cases, total = await store.list_cases(
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

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseRead:
    """Get a single case by ID with full context."""
    store = DbStore(session)
    case = await store.get_case(case_id)

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )

    return _case_to_read(case)


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor_id: str | None = Query(None, description="ID of the officer creating the case"),
) -> CaseRead:
    """Create a new case."""
    store = DbStore(session)
    audit = AuditService(session)

    # Validate client exists
    if await store.get_client(payload.client_id) is None:
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

    await store.add_case(case)

    await audit.log(
        event_type="case_created",
        case_id=case.id,
        client_id=case.client_id,
        actor_id=actor_id,
        actor_type="compliance_officer" if actor_id else "system",
        payload={
            "case_type": case.case_type.value,
            "jurisdiction": case.jurisdiction.value,
            "summary": case.context.summary,
        },
    )

    return _case_to_read(case)


@router.patch("/{case_id}/status", response_model=CaseRead)
async def update_case_status(
    case_id: UUID,
    new_status: CaseStatus,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor_id: str | None = Query(None, description="ID of the officer updating the status"),
) -> CaseRead:
    """Update a case's workflow status."""
    store = DbStore(session)
    audit = AuditService(session)

    # Read current status before overwriting so we can log the transition
    existing = await store.get_case(case_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    old_status = existing.status.value

    updated = await store.update_case(case_id, status=new_status)

    await audit.log(
        event_type="case_status_updated",
        case_id=case_id,
        actor_id=actor_id,
        actor_type="compliance_officer" if actor_id else "system",
        payload={
            "old_status": old_status,
            "new_status": new_status.value,
        },
    )

    return _case_to_read(updated)


@router.get(
    "/{case_id}/history",
    response_model=list[AuditEntryRead],
)
async def get_case_history(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor_id: str | None = Query(None, description="ID of the officer exporting the trail"),
) -> list[AuditEntryRead]:
    """
    Get the complete audit trail for a case.

    Returns all events (scoring, explanations, decisions) in chronological order.
    Used by UI "History" panel and regulatory export.
    """
    audit = AuditService(session)
    entries = await audit.export_case_trail(case_id)

    # Log that this trail was accessed / exported
    await audit.log(
        event_type="data_exported",
        case_id=case_id,
        actor_id=actor_id,
        actor_type="compliance_officer" if actor_id else "system",
        payload={
            "export_type": "case_audit_trail",
            "entries_exported": len(entries),
        },
    )

    return [
        AuditEntryRead(
            id=e.id,
            event_type=e.event_type,
            case_id=e.case_id,
            client_id=e.client_id,
            actor_id=e.actor_id,
            actor_type=e.actor_type,
            payload=e.payload,
            risk_score=e.risk_score,
            risk_level=e.risk_level,
            occurred_at=e.occurred_at,
        )
        for e in entries
    ]


def _case_to_read(case: Case) -> CaseRead:
    """Convert domain Case to API CaseRead."""
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
