"""
Common Pydantic models reused across the application.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TimestampedModel(BaseModel):
    """
    Base model with created_at / updated_at.
    
    Why a base class:
    - Consistency across all entities
    - Less boilerplate
    - Easy to add audit fields later
    """
    
    model_config = ConfigDict(
        from_attributes=True,  # Allow construction from ORM objects
        populate_by_name=True,  # Allow both alias and field name
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IdentifiedModel(TimestampedModel):
    """Base model with UUID + timestamps."""
    
    id: UUID = Field(default_factory=uuid4)


class PaginatedResponse(BaseModel):
    """
    Standard pagination wrapper for list endpoints.
    
    Usage:
        @router.get("/cases", response_model=PaginatedResponse[CaseRead])
        async def list_cases(...) -> PaginatedResponse[CaseRead]:
            ...
    """
    
    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20
    
    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total
    
    @property
    def has_prev(self) -> bool:
        return self.page > 1


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    
    error: str
    detail: str | None = None
    code: str | None = None
