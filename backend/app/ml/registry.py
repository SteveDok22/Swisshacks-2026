"""
Model Registry — single point of access for all ML models.

Pattern: Lazy-loaded singleton.
- Models load once at application startup (in main.py lifespan)
- All endpoints access models through get_registry()
- Fast lookup by case_type

When we add new case types (JB recommendation, Ripple AML),
we register new models here. The rest of the code doesn't change.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.base import RiskModel
from app.ml.extractors import SocialEngineeringFeatureExtractor
from app.schemas.enums import CaseType

logger = get_logger(__name__)


class ModelRegistry:
    """Holds all loaded ML models in memory."""
    
    def __init__(self) -> None:
        self._models: dict[CaseType, RiskModel] = {}
    
    def register(self, model: RiskModel) -> None:
        """Add a model to the registry."""
        self._models[model.case_type] = model
        logger.info(
            "model_registered",
            case_type=model.case_type,
            name=model.name,
            version=model.version,
        )
    
    def get(self, case_type: CaseType) -> RiskModel | None:
        """Look up a model by case type."""
        return self._models.get(case_type)
    
    def get_or_raise(self, case_type: CaseType) -> RiskModel:
        """Look up a model, raising if not found."""
        model = self._models.get(case_type)
        if model is None:
            available = list(self._models.keys())
            raise ValueError(
                f"No model registered for case_type={case_type}. "
                f"Available: {available}"
            )
        return model
    
    @property
    def loaded_case_types(self) -> list[CaseType]:
        return list(self._models.keys())
    
    def load_all(self, model_dir: Path | None = None) -> None:
        """
        Load all available models from disk.
        Called once at startup.
        
        If a model file doesn't exist, logs a warning but doesn't crash —
        we want the API to start even with no trained models (for dev).
        """
        model_dir = model_dir or Path(settings.model_dir)
        
        # === Social engineering model (AMINA) ===
        se_path = model_dir / "social_engineering_v1.joblib"
        if se_path.exists():
            extractor = SocialEngineeringFeatureExtractor()
            model = RiskModel.load(se_path, extractor)
            self.register(model)
        else:
            logger.warning(
                "model_file_missing",
                path=str(se_path),
                hint=(
                    "Run: python -m app.ml.training train-social-engineering"
                ),
            )
        
        # TODO День 14: Add Julius Baer model loading here
        # TODO День 14: Add Ripple model loading here
        
        logger.info(
            "registry_loaded",
            loaded_count=len(self._models),
            case_types=list(self._models.keys()),
        )


# === Singleton accessor ===
_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    """Get the singleton registry (lazy-initialized)."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
        _registry.load_all()
    return _registry


def reset_registry() -> None:
    """Reset registry (for tests)."""
    global _registry
    _registry = None
