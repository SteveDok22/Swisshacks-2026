"""
Clients API — read-only access to client information.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.logging import get_logger
from app.schemas.client import Client
from app.services.store import InMemoryStore, get_store

logger = get_logger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[Client])
async def list_clients(
    store: Annotated[InMemoryStore, Depends(get_store)],
) -> list[Client]:
    """List all clients."""
    return store.list_clients()


@router.get("/{client_id}", response_model=Client)
async def get_client(
    client_id: UUID,
    store: Annotated[InMemoryStore, Depends(get_store)],
) -> Client:
    """Get a single client by ID."""
    client = store.get_client(client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )
    return client
