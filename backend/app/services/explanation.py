"""
Explanation Service — ties together ML, Counterfactuals, Anonymizer, and Claude.

This is the FINAL LAYER of our backend pipeline:

    Case
     ↓
    RiskEngine (ML scoring + SHAP)
     ↓
    CounterfactualService (DiCE)
     ↓
    JurisdictionService (regulatory adjustments)
     ↓
    Anonymizer (remove PII)
     ↓
    Claude API (natural language)
     ↓
    Final explanation for compliance officer

Two flavors:
- generate() — non-streaming, returns full CaseExplanation
- stream_summary() — async generator yielding chunks for SSE

The frontend prefers streaming for the live "AI thinking" UX,
but the regular endpoint is essential for:
- Programmatic clients (audit log exports, batch processing)
- Testing
- Fallback when streaming fails
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.explanation import (
    AnonymizationPreview,
    CaseExplanation,
    ExplanationMetadata,
)
from app.services.anthropic_client import AnthropicClient, get_anthropic_client
from app.services.counterfactual import (
    CounterfactualService,
    get_counterfactual_service,
)
from app.services.jurisdiction import (
    JurisdictionService,
    get_jurisdiction_service,
)
from app.services.prompts import (
    COMPLIANCE_OFFICER_PERSONA,
    action_rationale_prompt,
    counterfactual_narrative_prompt,
    executive_summary_prompt,
    risk_factors_prompt,
)
from app.services.risk_engine import RiskEngine, get_risk_engine
from app.services.store import InMemoryStore, get_store
from app.utils.anonymizer import Anonymizer, get_anonymizer

logger = get_logger(__name__)


class ExplanationService:
    """Generates natural language explanations for risk-scored cases."""
    
    def __init__(
        self,
        store: InMemoryStore | None = None,
        risk_engine: RiskEngine | None = None,
        counterfactual_service: CounterfactualService | None = None,
        jurisdiction_service: JurisdictionService | None = None,
        anonymizer: Anonymizer | None = None,
        llm_client: AnthropicClient | None = None,
    ) -> None:
        self.store = store or get_store()
        self.risk_engine = risk_engine or get_risk_engine()
        self.cf_service = counterfactual_service or get_counterfactual_service()
        self.jurisdiction = jurisdiction_service or get_jurisdiction_service()
        self.anonymizer = anonymizer or get_anonymizer()
        self.llm = llm_client or get_anthropic_client()
    
    # === Full (non-streaming) explanation ===
    
    def generate(self, case_id: UUID) -> CaseExplanation:
        """
        Generate a complete natural language explanation.
        
        This runs the entire pipeline serially. For a UI that needs
        progressive feedback, use stream_summary() instead.
        """
        # === 1. Score the case ===
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        client = self.store.get_client(case.client_id)
        client_name = client.profile.full_name if client else None
        
        ml_result = self.risk_engine.score_case(case_id)
        
        # === 2. Anonymize case data BEFORE any LLM call ===
        # This is our privacy-by-design moment
        raw_data = dict(case.context.data)
        anon_report = self.anonymizer.anonymize_case_data(
            raw_data, client_name=client_name
        )
        
        # === 3. Prepare prompts (using anonymized data only) ===
        top_features_dicts = [
            f.model_dump() for f in ml_result.top_features
        ]
        
        # Executive summary
        exec_prompt = executive_summary_prompt(
            case_type=case.case_type.value,
            risk_score=ml_result.score,
            risk_level=ml_result.level.value,
            recommended_action=ml_result.recommended_action.value,
            top_features=top_features_dicts,
            anonymized_context=anon_report.anonymized,
            jurisdiction=case.jurisdiction.value,
        )
        executive_summary, exec_cached = self.llm.complete(
            exec_prompt, system=COMPLIANCE_OFFICER_PERSONA
        )
        
        # Risk factors deep-dive
        risk_prompt = risk_factors_prompt(
            risk_score=ml_result.score,
            risk_level=ml_result.level.value,
            top_features=top_features_dicts,
            anonymized_context=anon_report.anonymized,
        )
        risk_factors, _ = self.llm.complete(
            risk_prompt, system=COMPLIANCE_OFFICER_PERSONA
        )
        
        # Counterfactuals (only for non-low cases)
        alternative_outcomes: str | None = None
        if ml_result.level.value in ("high", "critical"):
            cf_result = self.cf_service.generate(case_id, n_scenarios=3)
            if cf_result.counterfactuals:
                cf_dicts = [cf.model_dump() for cf in cf_result.counterfactuals]
                cf_prompt = counterfactual_narrative_prompt(
                    original_score=ml_result.score,
                    counterfactuals=cf_dicts,
                )
                alternative_outcomes, _ = self.llm.complete(
                    cf_prompt, system=COMPLIANCE_OFFICER_PERSONA
                )
        
        # Action rationale (with jurisdiction)
        try:
            j_rules = self.jurisdiction.get_rules(case.jurisdiction)
            j_rules_dict = j_rules.model_dump()
            j_adjusted = self.jurisdiction.adjust_score(
                ml_result.score, case.jurisdiction, case, client
            )
            j_rules_dict["applicable_rules"] = j_adjusted.applicable_rules
        except Exception:
            j_rules_dict = {}
        
        action_prompt = action_rationale_prompt(
            recommended_action=ml_result.recommended_action.value,
            risk_score=ml_result.score,
            confidence=ml_result.confidence,
            jurisdiction=case.jurisdiction.value,
            jurisdiction_rules=j_rules_dict,
        )
        action_rationale, _ = self.llm.complete(
            action_prompt, system=COMPLIANCE_OFFICER_PERSONA
        )
        
        # Jurisdiction notes (from YAML, no LLM call needed)
        jurisdiction_notes = j_rules_dict.get("officer_notes")
        
        # === 4. Build response ===
        from app.core.config import settings
        metadata = ExplanationMetadata(
            model=settings.anthropic_model_main if not self.llm.is_mock else "mock",
            anonymization_applied=True,
            fields_redacted_count=len(anon_report.fields_redacted),
            fields_bucketed_count=len(anon_report.fields_bucketed),
            cached=exec_cached,
        )
        
        logger.info(
            "explanation_generated",
            case_id=str(case_id),
            llm_mode="mock" if self.llm.is_mock else "real",
            risk_level=ml_result.level.value,
        )
        
        return CaseExplanation(
            case_id=str(case_id),
            executive_summary=executive_summary,
            risk_factors=risk_factors,
            alternative_outcomes=alternative_outcomes,
            recommended_action_rationale=action_rationale,
            jurisdiction_notes=jurisdiction_notes,
            metadata=metadata,
        )
    
    # === Streaming (SSE) summary ===
    
    async def stream_summary(self, case_id: UUID) -> AsyncIterator[str]:
        """
        Stream the executive summary text chunk-by-chunk.
        
        Used by the SSE endpoint for live "AI thinking" UX.
        Frontend reads chunks and appends to display.
        """
        case = self.store.get_case(case_id)
        if case is None:
            yield f"[ERROR] Case {case_id} not found"
            return
        
        client = self.store.get_client(case.client_id)
        client_name = client.profile.full_name if client else None
        
        # Score first (this is synchronous, no streaming needed)
        ml_result = self.risk_engine.score_case(case_id)
        
        # Anonymize
        anon_report = self.anonymizer.anonymize_case_data(
            dict(case.context.data), client_name=client_name
        )
        
        # Build prompt
        top_features_dicts = [f.model_dump() for f in ml_result.top_features]
        prompt = executive_summary_prompt(
            case_type=case.case_type.value,
            risk_score=ml_result.score,
            risk_level=ml_result.level.value,
            recommended_action=ml_result.recommended_action.value,
            top_features=top_features_dicts,
            anonymized_context=anon_report.anonymized,
            jurisdiction=case.jurisdiction.value,
        )
        
        # Stream
        async for chunk in self.llm.stream(
            prompt, system=COMPLIANCE_OFFICER_PERSONA
        ):
            yield chunk
    
    # === Anonymization preview ===
    # Critical UI feature: show "what goes to AI vs what stays local"
    
    def get_anonymization_preview(
        self, case_id: UUID
    ) -> AnonymizationPreview:
        """
        Returns side-by-side view of data sent to AI vs kept local.
        
        Used by the UI's "Privacy" panel — a visible feature that
        demonstrates FINMA-compliant data handling.
        """
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        client = self.store.get_client(case.client_id)
        client_name = client.profile.full_name if client else None
        
        anon_report = self.anonymizer.anonymize_case_data(
            dict(case.context.data), client_name=client_name
        )
        
        # Determine which fields stay local (everything not in anonymized output)
        all_keys = set(anon_report.original.keys())
        anonymized_keys = set(anon_report.anonymized.keys())
        kept_local = list(all_keys - anonymized_keys - set(anon_report.fields_redacted))
        
        # Fields sent to AI (anonymized values)
        sent_to_ai = {
            k: str(v) for k, v in anon_report.anonymized.items()
        }
        
        return AnonymizationPreview(
            fields_kept_local=kept_local + anon_report.fields_redacted,
            fields_sent_to_ai=sent_to_ai,
            fields_redacted=anon_report.fields_redacted,
            fields_bucketed=anon_report.fields_bucketed,
        )


# Singleton
_service: ExplanationService | None = None


def get_explanation_service() -> ExplanationService:
    """FastAPI dependency."""
    global _service
    if _service is None:
        _service = ExplanationService()
    return _service
