"""
Application configuration using Pydantic Settings.
All settings are loaded from environment variables or .env file.
"""

from functools import lru_cache
from typing import Final, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# === Drift Engine scoring ===
# Keep the MVP's hand-tuned fusion parameters explicit until the planned
# learned fusion model replaces them.
DRIFT_INTERNAL_VELOCITY_WEIGHT: Final[float] = 0.60
DRIFT_INTERNAL_ACCUMULATED_WEIGHT: Final[float] = 0.25
DRIFT_INTERNAL_CONTAGION_WEIGHT: Final[float] = 0.40
DRIFT_PUBLIC_RISK_WEIGHT: Final[float] = 0.85
DRIFT_CONFIRMATION_LIFT_RANGE: Final[float] = 3.0
DRIFT_CONFIRMATION_MAX_AMPLIFICATION: Final[float] = 0.35


class Settings(BaseSettings):
    """
    Centralized application settings.

    Why Pydantic Settings:
    - Type-safe config (no magic strings)
    - Auto-loads from .env
    - Validation on startup (fail fast)
    - Easy to test (override via env vars)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === App ===
    app_name: str = "SwissHacks Risk Intelligence Platform"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # === CORS ===
    # Frontend URL for CORS - в проде это будет наш domain
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"]
    )

    # === Database ===
    database_url: str = "sqlite+aiosqlite:///./data/risk_platform.db"

    # === LLM ===
    anthropic_api_key: str = ""
    anthropic_model_main: str = "claude-sonnet-4-5"
    anthropic_model_fast: str = "claude-haiku-4-5"
    anthropic_max_tokens: int = 1024

    # === External news sources ===
    # Optional paid enhancement alongside free GDELT. When absent the adapter
    # returns [] and GDELT remains the always-on fallback.
    event_registry_api_key: str = ""

    # === ML ===
    model_dir: str = "./data/models"
    enable_dice_counterfactuals: bool = True
    enable_local_embeddings: bool = True

    # === Privacy ===
    # Ключевое: никогда не отправляем raw client data в LLM
    anonymize_before_llm: bool = True

    # === Audit ===
    audit_log_enabled: bool = True

    # === Jurisdictions ===
    default_jurisdiction: Literal["CH", "EU", "HK", "AE"] = "CH"
    jurisdictions_dir: str = "./app/jurisdictions"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.
    Use this everywhere via dependency injection.
    """
    return Settings()


# Convenient global access (use sparingly, prefer DI)
settings = get_settings()
