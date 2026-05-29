"""
Database-backed store (replaces InMemoryStore).

Provides the SAME INTERFACE as InMemoryStore so existing services
(RiskEngine, ExplanationService, etc.) work unchanged.

Key difference: persistent across restarts, true SQL filtering,
ready for production scaling.

Pattern: Async repository — each method takes a session and returns
domain objects (Pydantic schemas), not DB models. This keeps DB
details out of the rest of the codebase.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.db.models import CaseDB, ClientDB
from app.schemas.case import Case, CaseContext
from app.schemas.client import Client, ClientProfile

logger = get_logger(__name__)


class DbStore:
    """Database-backed CRUD operations."""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    # === Clients ===
    
    async def list_clients(self) -> list[Client]:
        """Return all clients as domain objects."""
        statement = select(ClientDB)
        result = await self.session.execute(statement)
        return [self._client_db_to_domain(c) for c in result.scalars().all()]
    
    async def get_client(self, client_id: UUID) -> Client | None:
        """Look up a client by ID."""
        statement = select(ClientDB).where(ClientDB.id == client_id)
        result = await self.session.execute(statement)
        client_db = result.scalar_one_or_none()
        if client_db is None:
            return None
        return self._client_db_to_domain(client_db)
    
    # === Cases ===
    
    async def list_cases(
        self,
        *,
        case_type: str | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Case], int]:
        """Filtered + paginated list of cases."""
        statement = select(CaseDB)
        
        if case_type:
            statement = statement.where(CaseDB.case_type == case_type)
        if status:
            statement = statement.where(CaseDB.status == status)
        if jurisdiction:
            statement = statement.where(CaseDB.jurisdiction == jurisdiction)
        
        # Most recent first
        statement = statement.order_by(CaseDB.created_at.desc())
        
        # Apply pagination
        statement = statement.offset(offset).limit(limit)
        
        result = await self.session.execute(statement)
        cases_db = list(result.scalars().all())
        
        # Get total (separate count query)
        count_stmt = select(CaseDB.id)
        if case_type:
            count_stmt = count_stmt.where(CaseDB.case_type == case_type)
        if status:
            count_stmt = count_stmt.where(CaseDB.status == status)
        if jurisdiction:
            count_stmt = count_stmt.where(CaseDB.jurisdiction == jurisdiction)
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        
        return [self._case_db_to_domain(c) for c in cases_db], total
    
    async def get_case(self, case_id: UUID) -> Case | None:
        """Look up a case by ID."""
        statement = select(CaseDB).where(CaseDB.id == case_id)
        result = await self.session.execute(statement)
        case_db = result.scalar_one_or_none()
        if case_db is None:
            return None
        return self._case_db_to_domain(case_db)
    
    async def add_case(self, case: Case) -> Case:
        """Persist a new case."""
        case_db = CaseDB(
            id=case.id,
            client_id=case.client_id,
            case_type=case.case_type,
            jurisdiction=case.jurisdiction,
            status=case.status,
            summary=case.context.summary,
            context_data=case.context.data,
            risk_score=case.risk_score,
            risk_level=case.risk_level,
            confidence=case.confidence,
            assigned_to=case.assigned_to,
            created_at=case.created_at,
            updated_at=case.updated_at,
            scored_at=case.scored_at,
            resolved_at=case.resolved_at,
        )
        self.session.add(case_db)
        await self.session.flush()
        return case
    
    async def update_case(self, case_id: UUID, **updates) -> Case | None:
        """Update case fields and return updated domain object."""
        statement = select(CaseDB).where(CaseDB.id == case_id)
        result = await self.session.execute(statement)
        case_db = result.scalar_one_or_none()
        if case_db is None:
            return None
        
        for key, value in updates.items():
            if hasattr(case_db, key):
                setattr(case_db, key, value)
        case_db.updated_at = datetime.utcnow()
        
        self.session.add(case_db)
        await self.session.flush()
        return self._case_db_to_domain(case_db)
    
    # === Converters ===
    
    def _client_db_to_domain(self, client_db: ClientDB) -> Client:
        """Convert DB row to domain object."""
        profile_data = client_db.profile_data or {}
        
        profile = ClientProfile(
            full_name=client_db.full_name,
            email=client_db.email,
            date_of_birth=profile_data.get("date_of_birth"),
            nationality=client_db.nationality,
            residence_country=client_db.residence_country,
            primary_jurisdiction=client_db.primary_jurisdiction,
            onboarded_at=client_db.onboarded_at,
            risk_tolerance=client_db.risk_tolerance,
            aum_chf=client_db.aum_chf,
            esg_focus=client_db.esg_focus,
            preferred_asset_classes=profile_data.get(
                "preferred_asset_classes", []
            ),
            is_pep=client_db.is_pep,
            sanctions_check_passed=client_db.sanctions_check_passed,
            last_review_date=client_db.last_review_date,
            typical_transaction_hours=profile_data.get(
                "typical_transaction_hours", list(range(8, 19))
            ),
            typical_transaction_currency=profile_data.get(
                "typical_transaction_currency", "CHF"
            ),
            whitelist_wallets=profile_data.get("whitelist_wallets", []),
        )
        
        return Client(
            id=client_db.id,
            profile=profile,
            created_at=client_db.created_at,
            updated_at=client_db.updated_at,
        )
    
    def _case_db_to_domain(self, case_db: CaseDB) -> Case:
        """Convert DB row to domain object."""
        return Case(
            id=case_db.id,
            client_id=case_db.client_id,
            case_type=case_db.case_type,
            jurisdiction=case_db.jurisdiction,
            status=case_db.status,
            context=CaseContext(
                summary=case_db.summary,
                data=case_db.context_data or {},
            ),
            risk_score=case_db.risk_score,
            risk_level=case_db.risk_level,
            confidence=case_db.confidence,
            assigned_to=case_db.assigned_to,
            created_at=case_db.created_at,
            updated_at=case_db.updated_at,
            scored_at=case_db.scored_at,
            resolved_at=case_db.resolved_at,
        )
