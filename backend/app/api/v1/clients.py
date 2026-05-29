"""
Clients API — async DB version.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.client import Client
from app.services.db_store import DbStore

logger = get_logger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[Client])
async def list_clients(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Client]:
    """List all clients."""
    store = DbStore(session)
    return await store.list_clients()


@router.get("/{client_id}", response_model=Client)
async def get_client(
    client_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Client:
    """Get a single client by ID."""
    store = DbStore(session)
    client = await store.get_client(client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )
    return client
