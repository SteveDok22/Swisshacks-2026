"""
Config endpoint — exposes the platform's current operating mode.

Returns the synthetic vs live mode status, LLM mode, and active source adapters
so the frontend can display an accurate indicator without hard-coding env vars.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.sources.registry import usable_adapters

router = APIRouter(prefix="/config", tags=["config"])


class ConfigResponse(BaseModel):
    mode: Literal["synthetic", "live"]
    external_apis_enabled: bool
    llm_mode: Literal["mock", "live"]
    active_adapters: list[str]


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return the platform's current operating mode.

    - ``mode``: ``"live"`` when ``EXTERNAL_APIS_ENABLED=1``; ``"synthetic"`` otherwise.
    - ``external_apis_enabled``: the raw boolean config value.
    - ``llm_mode``: ``"live"`` when ``ANTHROPIC_API_KEY`` is set; ``"mock"`` otherwise.
    - ``active_adapters``: the ``source_name`` of every adapter that is currently
      usable (free / free-tier, ``status == PLANNED``).
    """
    external_apis_enabled = settings.external_apis_enabled
    mode: Literal["synthetic", "live"] = "live" if external_apis_enabled else "synthetic"
    llm_mode: Literal["mock", "live"] = "live" if settings.anthropic_api_key else "mock"
    active_adapters = [a.source_name for a in usable_adapters()]
    return ConfigResponse(
        mode=mode,
        external_apis_enabled=external_apis_enabled,
        llm_mode=llm_mode,
        active_adapters=active_adapters,
    )
