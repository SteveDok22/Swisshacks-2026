"""
Counterfactual Service — async DB version.

DiCE-based "what-if" analysis.
"""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

warnings.filterwarnings("ignore", category=UserWarning)

from app.core.logging import get_logger
from app.ml.base import RiskModel
from app.ml.registry import ModelRegistry, get_registry
from app.ml.training import generate_synthetic_social_engineering_data
from app.schemas.counterfactual import (
    Counterfactual,
    CounterfactualResponse,
    FeatureChange,
)
from app.schemas.enums import CaseType
from app.services.db_store import DbStore

logger = get_logger(__name__)


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
        "client_aum_log",
    ],
}


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
    """Async DB version of CounterfactualService."""
    
    # Class-level caches (shared across requests — DiCE is expensive)
    _dice_cache: dict[CaseType, Any] = {}
    _training_data: dict[CaseType, pd.DataFrame] = {}
    
    def __init__(
        self,
        session: AsyncSession,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.session = session
        self.store = DbStore(session)
        self.registry = registry or get_registry()
    
    def _get_training_data(self, case_type: CaseType) -> pd.DataFrame:
        """Get cached training data for a case type."""
        if case_type not in self._training_data:
            if case_type == CaseType.SOCIAL_ENGINEERING:
                df = generate_synthetic_social_engineering_data(n_samples=3000)
                self._training_data[case_type] = df
            else:
                raise ValueError(f"No training data for {case_type}")
        return self._training_data[case_type]
    
    def _get_dice_explainer(self, case_type: CaseType, model: RiskModel) -> Any:
        if case_type in self._dice_cache:
            return self._dice_cache[case_type]
        
        from dice_ml import Data, Dice, Model
        
        df = self._get_training_data(case_type)
        feature_names = model.feature_extractor.feature_names
        variable_features = _VARIABLE_FEATURES_BY_CASE_TYPE.get(case_type, [])
        
        data_interface = Data(
            dataframe=df[feature_names + ["label"]],
            continuous_features=variable_features,
            outcome_name="label",
        )
        model_interface = Model(model=model.model, backend="sklearn")
        explainer = Dice(data_interface, model_interface, method="random")
        
        self._dice_cache[case_type] = explainer
        logger.info("dice_explainer_built", case_type=case_type.value)
        return explainer
    
    async def generate(
        self,
        case_id: UUID,
        n_scenarios: int = 3,
    ) -> CounterfactualResponse:
        """Generate counterfactuals for a case."""
        case = await self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        model = self.registry.get_or_raise(case.case_type)
        
        client = await self.store.get_client(case.client_id)
        client_context = self._build_client_context(client)
        features = model.feature_extractor.extract(case, client_context)
        feature_names = model.feature_extractor.feature_names
        
        query_df = pd.DataFrame([{
            name: features.get(name, 0.0) for name in feature_names
        }])
        
        proba = model.model.predict_proba(query_df)[0]
        original_score = float(proba[1]) * 100
        original_class = int(proba[1] > 0.5)
        original_outcome = "high_risk" if original_class == 1 else "low_risk"
        
        if original_class == 0:
            return CounterfactualResponse(
                case_id=str(case_id),
                original_score=round(original_score, 2),
                original_outcome=original_outcome,
                counterfactuals=[],
                notes="Case is already low-risk. Counterfactuals not generated.",
            )
        
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
        
        counterfactuals = []
        for idx, cf_row in enumerate(cf_df.itertuples(index=False), start=1):
            cf_dict = cf_row._asdict()
            
            changes = []
            for feat in variable_features:
                orig_val = float(query_df[feat].iloc[0])
                new_val = float(cf_dict.get(feat, orig_val))
                
                if abs(new_val - orig_val) > max(abs(orig_val) * 0.05, 0.1):
                    template = _CHANGE_TEMPLATES.get(feat, f"{feat} were {{value}}")
                    description = template.format(value=new_val, original=orig_val)
                    
                    changes.append(FeatureChange(
                        feature=feat,
                        original_value=round(orig_val, 2),
                        counterfactual_value=round(new_val, 2),
                        change_description=description,
                    ))
            
            if changes:
                top_changes = changes[:2]
                summary_parts = [c.change_description for c in top_changes]
                summary = (
                    "If " + " and ".join(summary_parts)
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
        
        return CounterfactualResponse(
            case_id=str(case_id),
            original_score=round(original_score, 2),
            original_outcome=original_outcome,
            counterfactuals=counterfactuals,
        )
    
    def _build_client_context(self, client) -> dict:
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
