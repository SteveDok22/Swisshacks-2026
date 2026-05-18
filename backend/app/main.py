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
from app.ml.registry import get_registry
from app.services.store import get_store

# Initialize logging FIRST, before anything else
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan: startup and shutdown logic.
    
    Use this to:
    - Load ML models into memory (so they're ready for first request)
    - Initialize database connections
    - Warm up caches
    - On shutdown: close connections, flush logs
    """
    # === STARTUP ===
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.environment,
    )
    
    # Seed in-memory store with mock data
    store = get_store()
    logger.info(
        "store_initialized",
        clients=len(store.clients),
        cases=len(store.cases),
    )
    
    # Load ML models into registry
    registry = get_registry()
    logger.info(
        "ml_models_loaded",
        loaded_count=len(registry.loaded_case_types),
        case_types=[ct.value for ct in registry.loaded_case_types],
    )
    
    # TODO День 6: Initialize database here
    
    logger.info("application_ready")
    
    yield  # Application runs here
    
    # === SHUTDOWN ===
    logger.info("application_shutting_down")


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

# === Middleware ===
# CORS — allow our frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Health check endpoint ===
# Always have this. Kubernetes/Docker uses it to know if app is alive.
@app.get("/health", tags=["meta"])
async def health_check() -> dict[str, str]:
    """Liveness probe — confirms the app is running."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    """Root endpoint — basic info."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
    }


# === API Routers ===
app.include_router(api_router, prefix=settings.api_v1_prefix)
