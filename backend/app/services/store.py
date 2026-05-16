"""
In-memory data store for development.

Why in-memory now:
- No DB setup overhead during early development
- Fast iteration
- Easy to reset (just restart the server)
- Will be replaced by SQLite on Day 6 with same interface

Pattern: Singleton-ish via module-level dict, accessed via get_store().
"""

from __future__ import annotations

from uuid import UUID

from app.core.logging import get_logger
from app.schemas.case import Case
from app.schemas.client import Client
from app.services.mock_data import generate_mock_cases, generate_mock_clients

logger = get_logger(__name__)


class InMemoryStore:
    """
    Thread-unsafe in-memory storage.
    For dev only — we'll swap this for SQLite on Day 6.
    
    Why a class instead of dicts:
    - Single place to swap implementation later
    - Easier to inject as dependency
    - Methods describe intent (find_case_by_id vs cases[id])
    """
    
    def __init__(self) -> None:
        self.clients: dict[UUID, Client] = {}
        self.cases: dict[UUID, Case] = {}
        self._initialized = False
    
    def seed(self) -> None:
        """Load mock data. Idempotent."""
        if self._initialized:
            logger.debug("store_already_seeded")
            return
        
        # Seed clients
        for client in generate_mock_clients():
            self.clients[client.id] = client
        
        # Seed cases
        for case in generate_mock_cases(list(self.clients.values())):
            self.cases[case.id] = case
        
        self._initialized = True
        logger.info(
            "store_seeded",
            client_count=len(self.clients),
            case_count=len(self.cases),
        )
    
    # === Clients ===
    
    def list_clients(self) -> list[Client]:
        return list(self.clients.values())
    
    def get_client(self, client_id: UUID) -> Client | None:
        return self.clients.get(client_id)
    
    def add_client(self, client: Client) -> Client:
        self.clients[client.id] = client
        return client
    
    # === Cases ===
    
    def list_cases(
        self,
        *,
        case_type: str | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Case], int]:
        """Filtered + paginated list of cases."""
        cases = list(self.cases.values())
        
        if case_type:
            cases = [c for c in cases if c.case_type == case_type]
        if status:
            cases = [c for c in cases if c.status == status]
        if jurisdiction:
            cases = [c for c in cases if c.jurisdiction == jurisdiction]
        
        # Most recent first
        cases.sort(key=lambda c: c.created_at, reverse=True)
        
        total = len(cases)
        return cases[offset : offset + limit], total
    
    def get_case(self, case_id: UUID) -> Case | None:
        return self.cases.get(case_id)
    
    def add_case(self, case: Case) -> Case:
        self.cases[case.id] = case
        return case
    
    def update_case(self, case_id: UUID, **updates) -> Case | None:
        case = self.cases.get(case_id)
        if case is None:
            return None
        
        updated = case.model_copy(update=updates)
        self.cases[case_id] = updated
        return updated


# === Singleton accessor ===
_store: InMemoryStore | None = None


def get_store() -> InMemoryStore:
    """
    Get the singleton store instance.
    Used as a FastAPI dependency.
    """
    global _store
    if _store is None:
        _store = InMemoryStore()
        _store.seed()
    return _store
