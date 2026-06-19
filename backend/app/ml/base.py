"""
Base classes for ML models.

Architecture: Strategy Pattern
- RiskModel: shared scoring/explanation logic for ALL use cases
- FeatureExtractor: per-use-case logic to turn Case → feature vector

This is the HEART of our universal architecture.
When a new challenge appears at the hackathon, we add a new
FeatureExtractor — the rest of the code is reused.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

from app.core.logging import get_logger
from app.schemas.case import Case
from app.schemas.enums import CaseType, DecisionAction, RiskLevel
from app.schemas.scoring import FeatureContribution, RiskScoreResult

logger = get_logger(__name__)


# === Risk score → level mapping ===
# Single source of truth, used everywhere.
def score_to_level(score: float) -> RiskLevel:
    """Map numeric score (0-100) to categorical risk level."""
    if score < 31:
        return RiskLevel.LOW
    elif score < 61:
        return RiskLevel.MEDIUM
    elif score < 86:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


def score_to_action(score: float, confidence: float) -> DecisionAction:
    """
    Recommended action based on score + confidence.
    
    Logic:
    - Low score → allow regardless
    - Medium score → step-up verification
    - High score with high confidence → block
    - High score with low confidence → escalate (human review)
    """
    if score <= 30:
        return DecisionAction.ALLOW
    
    if score <= 60:
        return DecisionAction.STEP_UP_VERIFICATION
    
    # High or critical scores
    if confidence >= 0.85:
        return DecisionAction.BLOCK
    else:
        return DecisionAction.ESCALATE


# === Feature Extractor base class ===
class FeatureExtractor(ABC):
    """
    Converts a Case into a feature vector for the ML model.
    
    Each case_type has its own subclass.
    """
    
    # Override in subclass — list of feature names in order
    feature_names: list[str] = []
    
    # Optional: human-readable labels for each feature
    feature_labels: dict[str, str] = {}
    
    @abstractmethod
    def extract(self, case: Case, client_context: dict | None = None) -> dict[str, float]:
        """
        Extract features from a case.
        
        Returns:
            dict mapping feature_name → value (must match self.feature_names)
        """
        raise NotImplementedError
    
    def to_dataframe(self, features: dict[str, float]) -> pd.DataFrame:
        """Convert feature dict to single-row DataFrame in correct column order."""
        # Ensure all features are present (fill missing with 0)
        row = {name: features.get(name, 0.0) for name in self.feature_names}
        return pd.DataFrame([row], columns=self.feature_names)
    
    def humanize_feature(self, name: str, value: float) -> str:
        """Convert a feature into a human-readable label for the UI."""
        template = self.feature_labels.get(name, name.replace("_", " ").capitalize())
        try:
            return template.format(value=value)
        except (KeyError, IndexError):
            return f"{template}: {value:.2f}"


# === Base ML model ===
class RiskModel:
    """
    Universal risk scoring model.
    
    Wraps an XGBoost classifier + SHAP explainer.
    All case types use the same RiskModel — only feature extractors differ.
    
    Critical PP5 lesson applied: SHAP TreeExplainer is computed on-the-fly,
    not pickled (avoids version compatibility issues across environments).
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        case_type: CaseType,
        feature_extractor: FeatureExtractor,
        model: xgb.XGBClassifier | None = None,
    ):
        self.name = name
        self.version = version
        self.case_type = case_type
        self.feature_extractor = feature_extractor
        self.model = model
        self._explainer: shap.TreeExplainer | None = None
    
    # === Properties ===
    
    @property
    def is_trained(self) -> bool:
        return self.model is not None
    
    @property
    def explainer(self) -> shap.TreeExplainer:
        """
        Lazy-load SHAP explainer.
        
        PP5 lesson: Don't pickle the explainer. Build it from the model
        on first use. This avoids `pickle` incompatibility issues
        between development (your Mac) and production (Docker).
        """
        if self._explainer is None:
            if self.model is None:
                raise RuntimeError(f"Model {self.name} not trained")
            self._explainer = shap.TreeExplainer(self.model)
        return self._explainer
    
    # === Inference ===
    
    def score(
        self,
        case: Case,
        client_context: dict | None = None,
    ) -> RiskScoreResult:
        """
        Run full scoring pipeline on a case.
        
        Steps:
        1. Extract features (case_type-specific)
        2. Run XGBoost prediction
        3. Compute SHAP values
        4. Build top-features list with human labels
        5. Return structured result
        """
        if self.model is None:
            raise RuntimeError(f"Model {self.name} not loaded")
        
        # 1. Feature extraction
        features = self.feature_extractor.extract(case, client_context)
        feature_df = self.feature_extractor.to_dataframe(features)
        
        # 2. Prediction
        # predict_proba returns [P(class=0), P(class=1)]
        proba = self.model.predict_proba(feature_df)[0]
        risk_proba = float(proba[1])  # probability of "risky" class
        score = risk_proba * 100  # 0-100 scale
        
        # Confidence: how decisive is the model
        # If proba is 0.5/0.5 — confidence low; if 0.95/0.05 — high
        confidence = float(max(proba) * 2 - 1) if max(proba) > 0.5 else 0.0
        confidence = max(0.0, min(1.0, confidence))
        
        # 3. SHAP values
        shap_values = self.explainer.shap_values(feature_df)
        # For binary XGBoost, shap_values is shape (1, n_features)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # positive class
        contributions = shap_values[0]  # first (only) row
        
        # 4. Top features
        feature_names = self.feature_extractor.feature_names
        feature_data = [
            {
                "name": name,
                "value": features.get(name, 0.0),
                "contribution": float(contributions[i]),
                "abs_contribution": abs(float(contributions[i])),
            }
            for i, name in enumerate(feature_names)
        ]
        # Sort by absolute contribution (most impactful first)
        feature_data.sort(key=lambda f: f["abs_contribution"], reverse=True)
        
        # Take top 5 and convert to FeatureContribution
        top_features = []
        for feat in feature_data[:5]:
            top_features.append(
                FeatureContribution(
                    name=feat["name"],
                    value=feat["value"],
                    contribution=feat["contribution"],
                    direction=(
                        "risk_increasing"
                        if feat["contribution"] > 0
                        else "risk_decreasing"
                    ),
                    human_label=self.feature_extractor.humanize_feature(
                        feat["name"], feat["value"]
                    ),
                )
            )
        
        logger.info(
            "case_scored",
            case_id=str(case.id),
            model=self.name,
            score=round(score, 2),
            confidence=round(confidence, 2),
        )
        
        return RiskScoreResult(
            score=round(score, 2),
            level=score_to_level(score),
            confidence=round(confidence, 3),
            recommended_action=score_to_action(score, confidence),
            top_features=top_features,
            model_name=self.name,
            model_version=self.version,
            scored_at=datetime.utcnow(),
            raw_features=features,
        )
    
    # === Persistence ===
    
    def save(self, path: Path) -> None:
        """Save model to disk (only the XGBoost object — not the explainer)."""
        if self.model is None:
            raise RuntimeError("Cannot save untrained model")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save metadata + model together
        artifact = {
            "name": self.name,
            "version": self.version,
            "case_type": self.case_type.value,
            "feature_names": self.feature_extractor.feature_names,
            "model": self.model,
        }
        joblib.dump(artifact, path)
        logger.info("model_saved", path=str(path), model=self.name)
    
    @classmethod
    def load(cls, path: Path, feature_extractor: FeatureExtractor) -> RiskModel:
        """Load a saved model from disk."""
        artifact = joblib.load(path)
        instance = cls(
            name=artifact["name"],
            version=artifact["version"],
            case_type=CaseType(artifact["case_type"]),
            feature_extractor=feature_extractor,
            model=artifact["model"],
        )
        logger.info("model_loaded", path=str(path), model=instance.name)
        return instance
