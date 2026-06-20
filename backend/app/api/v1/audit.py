"""
Audit Log API — search and export immutable event log.

This is the compliance backbone — if FINMA asks for audit trail,
this is what we hand them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.audit import AuditEntryRead, AuditQueryParams
from app.schemas.common import PaginatedResponse
from app.services.audit import AuditService

logger = get_logger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=PaginatedResponse)
async def search_audit_log(
    session: Annotated[AsyncSession, Depends(get_session)],
    event_type: str | None = Query(None, description="Filter by event type"),
    case_id: UUID | None = Query(None),
    drift_id: str | None = Query(None),
    actor_id: str | None = Query(None),
    risk_level: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> PaginatedResponse:
    """
    Search the audit log with filters.
    
    Supports filtering by event type, case, actor, risk level, date range.
    Used by:
    - Compliance officer review queue
    - Regulatory export
    - "All decisions by Anna Müller this week"
    """
    service = AuditService(session)
    
    params = AuditQueryParams(
        event_type=event_type,
        case_id=case_id,
        drift_id=drift_id,
        actor_id=actor_id,
        risk_level=risk_level,
        from_date=from_date,
        to_date=to_date,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    
    entries, total = await service.query(params)
    
    items = [
        AuditEntryRead(
            id=e.id,
            event_type=e.event_type,
            case_id=e.case_id,
            client_id=e.client_id,
            drift_id=e.drift_id,
            actor_id=e.actor_id,
            actor_type=e.actor_type,
            payload=e.payload,
            risk_score=e.risk_score,
            risk_level=e.risk_level,
            occurred_at=e.occurred_at,
        )
        for e in entries
    ]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
