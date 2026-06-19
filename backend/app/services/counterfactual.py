"""
Counterfactual Service — DiCE-based "what-if" analysis.

This is ONE OF OUR KEY DIFFERENTIATORS.
Other teams will show SHAP. We'll show SHAP + counterfactuals.

For a compliance officer, counterfactuals answer:
"Show me what would make this case acceptable" —
which is exactly the question they need to escalate
or rule-out concerns with the relationship manager.

Implementation notes:
- DiCE is computationally expensive (~500ms per call)
- We cache training data in memory (loaded once at startup)
- We use 'random' method for speed (genetic/kdtree are slower)
- We fix categorical features to avoid impossible counterfactuals
"""

from __future__ import annotations

import warnings
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd

# DiCE prints a lot of warnings; suppress for clean logs
warnings.filterwarnings("ignore", category=UserWarning)

from app.core.logging import get_logger
from app.ml.base import RiskModel, score_to_level
from app.ml.registry import ModelRegistry, get_registry
from app.ml.training import generate_synthetic_social_engineering_data
from app.schemas.counterfactual import (
    Counterfactual,
    CounterfactualResponse,
    FeatureChange,
)
from app.schemas.enums import CaseType
from app.services.store import InMemoryStore, get_store

logger = get_logger(__name__)


# Features that DiCE can vary (continuous/orderable)
# We include all numeric features (even if some are "static" like AUM)
# to give DiCE flexibility in the feasibility region.
_VARIABLE_FEATURES_BY_CASE_TYPE: dict[CaseType, list[str]] = {
    CaseType.SOCIAL_ENGINEERING: [
        "amount_chf_log",
        "amount_vs_typical_ratio",
        "hour_of_day",
        "hour_deviation_from_typical",
        "destination_country_risk",
        "urgency_signals",
        "secrecy_signals",
        "pressure_signals",
        "transcript_length",
        "days_since_last_review",
        "client_aum_log",  # Static but needed for DiCE feasibility
    ],
}


# Human-readable change templates
_CHANGE_TEMPLATES: dict[str, str] = {
    "amount_chf_log": "amount were {value}",
    "amount_vs_typical_ratio": "amount were {value:.1f}x typical (vs current {original:.1f}x)",
    "hour_of_day": "request submitted at {value:.0f}:00 (vs current {original:.0f}:00)",
    "hour_deviation_from_typical": "request within typical hours (vs {original:.0f}h deviation)",
    "destination_country_risk": "destination were lower-risk country ({value:.2f} vs {original:.2f})",
    "urgency_signals": "fewer urgency markers ({value:.0f} vs {original:.0f})",
    "secrecy_signals": "fewer secrecy markers ({value:.0f} vs {original:.0f})",
    "pressure_signals": "fewer pressure tactics ({value:.0f} vs {original:.0f})",
    "transcript_length": "more thorough conversation ({value:.0f} vs {original:.0f} words)",
    "days_since_last_review": "more recent compliance review ({value:.0f} vs {original:.0f} days)",
}


class CounterfactualService:
    """
    Generates "what-would-change-the-decision" scenarios.
    
    Uses DiCE (Diverse Counterfactual Explanations) from Microsoft Research.
    """
    
    def __init__(
        self,
        store: InMemoryStore | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.store = store or get_store()
        self.registry = registry or get_registry()
        # Cache DiCE explainers per case_type (expensive to build)
        self._dice_cache: dict[CaseType, Any] = {}
        # Cache training data for DiCE
        self._training_data: dict[CaseType, pd.DataFrame] = {}
    
    def _get_training_data(self, case_type: CaseType) -> pd.DataFrame:
        """Get cached training data for a case type."""
        if case_type not in self._training_data:
            if case_type == CaseType.SOCIAL_ENGINEERING:
                # Larger sample for better feature coverage in DiCE
                df = generate_synthetic_social_engineering_data(n_samples=3000)
                self._training_data[case_type] = df
            else:
                raise ValueError(f"No training data for {case_type}")
        return self._training_data[case_type]
    
    def _get_dice_explainer(self, case_type: CaseType, model: RiskModel) -> Any:
        """Get cached DiCE explainer for a case type."""
        if case_type in self._dice_cache:
            return self._dice_cache[case_type]
        
        # Import here to avoid loading at module level
        from dice_ml import Data, Dice, Model
        
        df = self._get_training_data(case_type)
        feature_names = model.feature_extractor.feature_names
        
        # DiCE needs to know which features are continuous
        variable_features = _VARIABLE_FEATURES_BY_CASE_TYPE.get(case_type, [])
        
        data_interface = Data(
            dataframe=df[feature_names + ["label"]],
            continuous_features=variable_features,
            outcome_name="label",
        )
        model_interface = Model(model=model.model, backend="sklearn")
        
        # 'random' method is fastest (vs 'genetic', 'kdtree')
        explainer = Dice(data_interface, model_interface, method="random")
        
        self._dice_cache[case_type] = explainer
        logger.info("dice_explainer_built", case_type=case_type.value)
        
        return explainer
    
    def generate(
        self,
        case_id: UUID,
        n_scenarios: int = 3,
    ) -> CounterfactualResponse:
        """
        Generate counterfactuals for a case.
        
        Args:
            case_id: The case to analyze
            n_scenarios: How many alternative scenarios to generate
        
        Returns:
            CounterfactualResponse with original outcome + alternative scenarios
        """
        # Fetch case
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        # Get model
        model = self.registry.get_or_raise(case.case_type)
        
        # Extract features for this case
        client = self.store.get_client(case.client_id)
        client_context = self._build_client_context(client)
        features = model.feature_extractor.extract(case, client_context)
        feature_names = model.feature_extractor.feature_names
        
        query_df = pd.DataFrame([{
            name: features.get(name, 0.0) for name in feature_names
        }])
        
        # Current prediction
        proba = model.model.predict_proba(query_df)[0]
        original_score = float(proba[1]) * 100
        original_class = int(proba[1] > 0.5)
        original_outcome = "high_risk" if original_class == 1 else "low_risk"
        
        # If already low risk, no useful counterfactuals
        if original_class == 0:
            return CounterfactualResponse(
                case_id=str(case_id),
                original_score=round(original_score, 2),
                original_outcome=original_outcome,
                counterfactuals=[],
                notes=(
                    "Case is already low-risk. "
                    "Counterfactuals not generated."
                ),
            )
        
        # Generate counterfactuals (flip to class 0 = low risk)
        explainer = self._get_dice_explainer(case.case_type, model)
        variable_features = _VARIABLE_FEATURES_BY_CASE_TYPE.get(case.case_type, [])
        
        try:
            cf_result = explainer.generate_counterfactuals(
                query_df,
                total_CFs=n_scenarios,
                desired_class=0,
                features_to_vary=variable_features,
            )
        except Exception as e:
            logger.warning("counterfactual_generation_failed", error=str(e))
            return CounterfactualResponse(
                case_id=str(case_id),
                original_score=round(original_score, 2),
                original_outcome=original_outcome,
                counterfactuals=[],
                notes=f"Could not generate counterfactuals: {e}",
            )
        
        cf_df = cf_result.cf_examples_list[0].final_cfs_df
        
        if cf_df is None or len(cf_df) == 0:
            return CounterfactualResponse(
                case_id=str(case_id),
                original_score=round(original_score, 2),
                original_outcome=original_outcome,
                counterfactuals=[],
                notes="No counterfactuals found in feasible region.",
            )
        
        # Convert to schema objects
        counterfactuals = []
        for idx, cf_row in enumerate(cf_df.itertuples(index=False), start=1):
            cf_dict = cf_row._asdict()
            
            # Find changed features
            changes = []
            for feat in variable_features:
                orig_val = float(query_df[feat].iloc[0])
                new_val = float(cf_dict.get(feat, orig_val))
                
                # Only show meaningful changes (>5% difference)
                if abs(new_val - orig_val) > max(abs(orig_val) * 0.05, 0.1):
                    template = _CHANGE_TEMPLATES.get(feat, f"{feat} were {{value}}")
                    description = template.format(value=new_val, original=orig_val)
                    
                    changes.append(FeatureChange(
                        feature=feat,
                        original_value=round(orig_val, 2),
                        counterfactual_value=round(new_val, 2),
                        change_description=description,
                    ))
            
            # Summary string
            if changes:
                top_changes = changes[:2]
                summary_parts = [c.change_description for c in top_changes]
                summary = (
                    "If "
                    + " and ".join(summary_parts)
                    + " — this case would be approved."
                )
            else:
                summary = "Minor adjustments would flip the decision (sub-threshold)."
            
            counterfactuals.append(Counterfactual(
                scenario_id=idx,
                new_predicted_outcome="low_risk",
                changes=changes,
                summary=summary,
            ))
        
        logger.info(
            "counterfactuals_generated",
            case_id=str(case_id),
            count=len(counterfactuals),
        )
        
        return CounterfactualResponse(
            case_id=str(case_id),
            original_score=round(original_score, 2),
            original_outcome=original_outcome,
            counterfactuals=counterfactuals,
        )
    
    def _build_client_context(self, client) -> dict:
        """Mirror the logic from risk_engine."""
        from datetime import datetime
        if client is None:
            return {}
        profile = client.profile
        days_since_review = 90
        if profile.last_review_date:
            days_since_review = (
                datetime.utcnow().date() - profile.last_review_date
            ).days
        return {
            "aum_chf": profile.aum_chf,
            "is_pep": profile.is_pep,
            "typical_hours": profile.typical_transaction_hours,
            "typical_amount": profile.aum_chf * 0.02,
            "whitelist_wallets": profile.whitelist_wallets,
            "days_since_review": days_since_review,
        }


# Singleton
_service: CounterfactualService | None = None


def get_counterfactual_service() -> CounterfactualService:
    """FastAPI dependency."""
    global _service
    if _service is None:
        _service = CounterfactualService()
    return _service
