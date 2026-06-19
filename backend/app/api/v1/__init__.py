"""
API v1 — all version 1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import (
    audit,
    cases,
    clients,
    counterfactuals,
    decisions,
    explanations,
    jurisdictions,
    scoring,
)

api_router = APIRouter()

api_router.include_router(cases.router)
api_router.include_router(clients.router)
api_router.include_router(scoring.router)
api_router.include_router(counterfactuals.router)
api_router.include_router(jurisdictions.router)
api_router.include_router(explanations.router)
api_router.include_router(decisions.router)
api_router.include_router(audit.router)
