"""
Explanation Service — async DB version.

Orchestrates the full pipeline:
Case → ML → SHAP → DiCE → Anonymizer → Claude → Natural language
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.schemas.explanation import (
    AnonymizationPreview,
    CaseExplanation,
    ExplanationMetadata,
)
from app.services.anthropic_client import AnthropicClient, get_anthropic_client
from app.services.audit import AuditService
from app.services.counterfactual import CounterfactualService
from app.services.db_store import DbStore
from app.services.jurisdiction import JurisdictionService
from app.services.prompts import (
    COMPLIANCE_OFFICER_PERSONA,
    action_rationale_prompt,
    counterfactual_narrative_prompt,
    executive_summary_prompt,
    risk_factors_prompt,
)
from app.services.risk_engine import RiskEngine
from app.utils.anonymizer import Anonymizer, get_anonymizer

logger = get_logger(__name__)


class ExplanationService:
    """Generates natural language explanations for risk-scored cases."""
    
    def __init__(
        self,
        session: AsyncSession,
        anonymizer: Anonymizer | None = None,
        llm_client: AnthropicClient | None = None,
    ) -> None:
        self.session = session
        self.store = DbStore(session)
        self.audit = AuditService(session)
        self.risk_engine = RiskEngine(session)
        self.cf_service = CounterfactualService(session)
        self.jurisdiction = JurisdictionService(session)
        self.anonymizer = anonymizer or get_anonymizer()
        self.llm = llm_client or get_anthropic_client()
    
    async def generate(self, case_id: UUID, actor_id: str | None = None) -> CaseExplanation:
        """Generate complete natural language explanation."""
        case = await self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        client = await self.store.get_client(case.client_id)
        client_name = client.profile.full_name if client else None
        
        # Score
        ml_result = await self.risk_engine.score_case(case_id, actor_id=actor_id)
        
        # Anonymize BEFORE any LLM call
        raw_data = dict(case.context.data)
        anon_report = self.anonymizer.anonymize_case_data(
            raw_data, client_name=client_name
        )
        
        top_features_dicts = [f.model_dump() for f in ml_result.top_features]
        
        # === Executive summary ===
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
        
        # === Risk factors ===
        risk_prompt = risk_factors_prompt(
            risk_score=ml_result.score,
            risk_level=ml_result.level.value,
            top_features=top_features_dicts,
            anonymized_context=anon_report.anonymized,
        )
        risk_factors, _ = self.llm.complete(
            risk_prompt, system=COMPLIANCE_OFFICER_PERSONA
        )
        
        # === Counterfactuals (only for high/critical) ===
        alternative_outcomes: str | None = None
        if ml_result.level.value in ("high", "critical"):
            cf_result = await self.cf_service.generate(case_id, n_scenarios=3)
            if cf_result.counterfactuals:
                cf_dicts = [cf.model_dump() for cf in cf_result.counterfactuals]
                cf_prompt = counterfactual_narrative_prompt(
                    original_score=ml_result.score,
                    counterfactuals=cf_dicts,
                )
                alternative_outcomes, _ = self.llm.complete(
                    cf_prompt, system=COMPLIANCE_OFFICER_PERSONA
                )
        
        # === Action rationale ===
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
        
        jurisdiction_notes = j_rules_dict.get("officer_notes")
        
        # === Build response ===
        from app.core.config import settings
        metadata = ExplanationMetadata(
            model=settings.anthropic_model_main if not self.llm.is_mock else "mock",
            anonymization_applied=True,
            fields_redacted_count=len(anon_report.fields_redacted),
            fields_bucketed_count=len(anon_report.fields_bucketed),
            cached=exec_cached,
        )
        
        # Audit log
        await self.audit.log(
            event_type="explanation_generated",
            case_id=case_id,
            client_id=case.client_id,
            actor_id=actor_id,
            actor_type="compliance_officer" if actor_id else "system",
            risk_score=ml_result.score,
            risk_level=ml_result.level.value,
            payload={
                "llm_mode": "mock" if self.llm.is_mock else "real",
                "anonymization_applied": True,
                "fields_redacted_count": len(anon_report.fields_redacted),
                "fields_bucketed_count": len(anon_report.fields_bucketed),
                "had_counterfactuals": alternative_outcomes is not None,
            },
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
    
    async def stream_summary(self, case_id: UUID) -> AsyncIterator[str]:
        """Stream executive summary text chunk-by-chunk."""
        case = await self.store.get_case(case_id)
        if case is None:
            yield f"[ERROR] Case {case_id} not found"
            return
        
        client = await self.store.get_client(case.client_id)
        client_name = client.profile.full_name if client else None
        
        ml_result = await self.risk_engine.score_case(case_id)
        
        anon_report = self.anonymizer.anonymize_case_data(
            dict(case.context.data), client_name=client_name
        )
        
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
        
        async for chunk in self.llm.stream(
            prompt, system=COMPLIANCE_OFFICER_PERSONA
        ):
            yield chunk
    
    async def get_anonymization_preview(
        self, case_id: UUID
    ) -> AnonymizationPreview:
        """Returns side-by-side view of data sent to AI vs kept local."""
        case = await self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        client = await self.store.get_client(case.client_id)
        client_name = client.profile.full_name if client else None
        
        anon_report = self.anonymizer.anonymize_case_data(
            dict(case.context.data), client_name=client_name
        )
        
        all_keys = set(anon_report.original.keys())
        anonymized_keys = set(anon_report.anonymized.keys())
        kept_local = list(all_keys - anonymized_keys - set(anon_report.fields_redacted))
        
        sent_to_ai = {k: str(v) for k, v in anon_report.anonymized.items()}
        
        return AnonymizationPreview(
            fields_kept_local=kept_local + anon_report.fields_redacted,
            fields_sent_to_ai=sent_to_ai,
            fields_redacted=anon_report.fields_redacted,
            fields_bucketed=anon_report.fields_bucketed,
        )
