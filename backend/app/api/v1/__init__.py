"""
API v1 — all version 1 endpoints.

To add a new router:
1. Create app/api/v1/myresource.py with `router = APIRouter(...)`
2. Import it here
3. Include it in `api_router`
"""

from fastapi import APIRouter

from app.api.v1 import cases, clients

api_router = APIRouter()

api_router.include_router(cases.router)
api_router.include_router(clients.router)
