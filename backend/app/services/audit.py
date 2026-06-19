"""
Audit Service — immutable append-only logging.

This is THE COMPLIANCE BACKBONE.

Every meaningful event in the system passes through here:
- case_created
- case_scored
- explanation_generated
- decision_recorded
- counterfactuals_generated
- jurisdiction_compared
- data_exported

Operations:
- log()          — append a single entry (immutable)
- query()        — search entries with filters
- export()       — get full audit trail for a case

Note: There is NO update() or delete() method.
That's intentional — audit logs are append-only by regulation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from app.core.logging import get_logger
from app.db.models import AuditEntryDB
from app.schemas.audit import AuditEntryRead, AuditQueryParams

logger = get_logger(__name__)


class AuditService:
    """Append-only audit log service."""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    # === Logging (append-only) ===
    
    async def log(
        self,
        *,
        event_type: str,
        payload: dict[str, Any] | None = None,
        case_id: UUID | None = None,
        client_id: UUID | None = None,
        actor_id: str | None = None,
        actor_type: str = "system",
        risk_score: float | None = None,
        risk_level: str | None = None,
    ) -> AuditEntryDB:
        """
        Append a new audit entry.
        
        Returns the created entry (with assigned ID + timestamp).
        """
        entry = AuditEntryDB(
            event_type=event_type,
            payload=payload or {},
            case_id=case_id,
            client_id=client_id,
            actor_id=actor_id,
            actor_type=actor_type,
            risk_score=risk_score,
            risk_level=risk_level,
            occurred_at=datetime.utcnow(),
        )
        
        self.session.add(entry)
        await self.session.flush()  # Get the ID without committing
        
        logger.info(
            "audit_entry_logged",
            event_type=event_type,
            case_id=str(case_id) if case_id else None,
            actor_id=actor_id,
        )
        
        return entry
    
    # === Querying ===

    @staticmethod
    def _apply_filters(stmt, params: AuditQueryParams):
        """Apply all search filters to a statement. Single source of truth."""
        if params.event_type:
            stmt = stmt.where(AuditEntryDB.event_type == params.event_type)
        if params.case_id:
            stmt = stmt.where(AuditEntryDB.case_id == params.case_id)
        if params.client_id:
            stmt = stmt.where(AuditEntryDB.client_id == params.client_id)
        if params.actor_id:
            stmt = stmt.where(AuditEntryDB.actor_id == params.actor_id)
        if params.risk_level:
            stmt = stmt.where(AuditEntryDB.risk_level == params.risk_level)
        if params.from_date:
            stmt = stmt.where(AuditEntryDB.occurred_at >= params.from_date)
        if params.to_date:
            stmt = stmt.where(AuditEntryDB.occurred_at <= params.to_date)
        return stmt

    async def query(self, params: AuditQueryParams) -> tuple[list[AuditEntryDB], int]:
        """
        Search audit log with filters.

        Returns (entries, total_count).
        """
        base = self._apply_filters(select(AuditEntryDB), params)
        statement = base.order_by(desc(AuditEntryDB.occurred_at)).offset(params.offset).limit(params.limit)

        result = await self.session.execute(statement)
        entries = list(result.scalars().all())

        count_stmt = self._apply_filters(select(func.count()).select_from(AuditEntryDB), params)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return entries, total
    
    # === Export ===
    
    async def export_case_trail(self, case_id: UUID) -> list[AuditEntryDB]:
        """
        Get the complete audit trail for a single case.
        
        Used for:
        - "View History" panel in UI
        - Regulatory export
        - Compliance officer training (looking at past decisions)
        """
        statement = (
            select(AuditEntryDB)
            .where(AuditEntryDB.case_id == case_id)
            .order_by(AuditEntryDB.occurred_at)  # Chronological
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
