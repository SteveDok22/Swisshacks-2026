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
from app.ml.extractors import DriftFeatureExtractor, SocialEngineeringFeatureExtractor
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
        """
        Look up a model, with graceful fallback.
        
        If no model is registered for the requested case_type, we fall back to
        the social_engineering model as a behavioral baseline. The features
        partially generalize (amount-vs-typical, time anomalies, country risk),
        so we still get a meaningful score — just less specific than a
        purpose-trained model would give.
        
        This is intentional for the hackathon MVP: it lets us demo across
        multiple case types (investment recommendation, XRPL transactions)
        without training a separate model for each.
        
        Raises only if no models at all are loaded.
        """
        model = self._models.get(case_type)
        if model is not None:
            return model
        
        # Fallback: use social_engineering as baseline
        fallback = self._models.get(CaseType.SOCIAL_ENGINEERING)
        if fallback is not None:
            logger.info(
                "model_fallback_to_baseline",
                requested=case_type.value,
                fallback=fallback.case_type.value,
                reason="no_specific_model_trained",
            )
            return fallback
        
        # Nothing loaded — genuine error
        available = list(self._models.keys())
        raise ValueError(
            f"No model registered for case_type={case_type} and no fallback "
            f"available. Available: {available}. "
            f"Run: python -m app.ml.training train-social-engineering"
        )
    
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
        
        # === Drift model ===
        drift_path = model_dir / "drift_v1.joblib"
        if drift_path.exists():
            drift_extractor = DriftFeatureExtractor()
            drift_model = RiskModel.load(drift_path, drift_extractor)
            self.register(drift_model)
        else:
            logger.warning(
                "model_file_missing",
                path=str(drift_path),
                hint="Run: python -m app.ml.training train-drift",
            )

        # TODO: Add Julius Baer model loading here
        # TODO: Add Ripple model loading here

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
