"""
FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload

Run via Docker:
    docker compose up backend
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.seed import seed_if_empty
from app.db.session import close_db, init_db, session_scope
from app.ml.registry import get_registry
from app.services.jurisdiction import JurisdictionService

# Initialize logging FIRST
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown logic."""
    # === STARTUP ===
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.environment,
    )
    
    # Initialize database schema
    await init_db()
    
    # Seed with mock data if empty
    async with session_scope() as session:
        seeded = await seed_if_empty(session)
        if seeded:
            logger.info("database_seeded_with_mock_data")
    
    # Load ML models
    registry = get_registry()
    logger.info(
        "ml_models_loaded",
        loaded_count=len(registry.loaded_case_types),
        case_types=[ct.value for ct in registry.loaded_case_types],
    )
    
    # Pre-load jurisdiction rules (class-level cache)
    jurisdictions = JurisdictionService()
    logger.info(
        "jurisdictions_loaded",
        count=len(jurisdictions.loaded_jurisdictions),
        codes=[j.value for j in jurisdictions.loaded_jurisdictions],
    )
    
    logger.info("application_ready")
    
    yield
    
    # === SHUTDOWN ===
    logger.info("application_shutting_down")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Universal risk scoring platform with explainable AI",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health_check() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
    }


# === API Routers ===
app.include_router(api_router, prefix=settings.api_v1_prefix)
