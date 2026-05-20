"""
Jurisdiction Service — adapts ML scores to local regulatory contexts.

This is OUR DIFFERENTIATOR FOR AMINA.
AMINA operates under FINMA, MiCA (via Austria), SFC, FSRA — each with
different thresholds and requirements. AMINA's CPO has publicly named
this as a structural pain point.

Most teams will ignore jurisdiction. We will:
1. Load rules from YAML (auditable by compliance, no code changes needed)
2. Apply jurisdiction-specific score modifiers
3. Use jurisdiction-specific action thresholds
4. Surface jurisdiction-specific officer notes in the UI

Demo moment:
"Same case under FINMA → BLOCK. Under SFC → ESCALATE."
Toggle jurisdiction in the UI → see live recalculation.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import yaml

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.case import Case
from app.schemas.client import Client
from app.schemas.enums import DecisionAction, Jurisdiction
from app.schemas.jurisdiction import (
    JurisdictionAdjustedScore,
    JurisdictionRules,
)
from app.services.store import InMemoryStore, get_store

logger = get_logger(__name__)


class JurisdictionService:
    """Loads and applies jurisdiction-specific rules."""
    
    def __init__(
        self,
        rules_dir: Path | None = None,
        store: InMemoryStore | None = None,
    ) -> None:
        self.rules_dir = rules_dir or Path(settings.jurisdictions_dir)
        self.store = store or get_store()
        self._rules: dict[Jurisdiction, JurisdictionRules] = {}
        self._load_all()
    
    def _load_all(self) -> None:
        """Load all YAML files from jurisdictions/ directory."""
        for j in Jurisdiction:
            yaml_path = self.rules_dir / f"{j.value}.yaml"
            if not yaml_path.exists():
                logger.warning(
                    "jurisdiction_yaml_missing",
                    code=j.value,
                    path=str(yaml_path),
                )
                continue
            
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                rules = JurisdictionRules(**data)
                self._rules[j] = rules
                logger.info(
                    "jurisdiction_loaded",
                    code=j.value,
                    regulator=rules.regulator,
                )
            except Exception as e:
                logger.error(
                    "jurisdiction_load_failed",
                    code=j.value,
                    error=str(e),
                )
    
    @property
    def loaded_jurisdictions(self) -> list[Jurisdiction]:
        return list(self._rules.keys())
    
    def get_rules(self, jurisdiction: Jurisdiction) -> JurisdictionRules:
        """Get rules for a jurisdiction (raises if not loaded)."""
        if jurisdiction not in self._rules:
            raise ValueError(f"No rules loaded for {jurisdiction}")
        return self._rules[jurisdiction]
    
    def adjust_score(
        self,
        base_score: float,
        jurisdiction: Jurisdiction,
        case: Case,
        client: Client | None = None,
    ) -> JurisdictionAdjustedScore:
        """
        Apply jurisdiction-specific modifiers to a base ML score.
        
        Steps:
        1. Start with base ML score
        2. Apply multiplicative modifiers based on context (PEP, new dest, etc.)
        3. Use jurisdiction-specific action thresholds
        4. Cap at 100
        """
        rules = self.get_rules(jurisdiction)
        
        adjusted = base_score
        modifiers_applied: dict[str, float] = {}
        rules_triggered: list[str] = []
        
        # === Apply context-based modifiers ===
        case_data = case.context.data
        client_profile = client.profile if client else None
        
        # PEP modifier
        if client_profile and client_profile.is_pep:
            mod = rules.score_modifiers.get("client_is_pep", 1.0)
            if mod != 1.0:
                adjusted *= mod
                modifiers_applied["client_is_pep"] = mod
                rules_triggered.append(
                    f"PEP client: score ×{mod} (FINMA EDD requirement)"
                )
        
        # New destination wallet
        dest_wallet = case_data.get("destination_wallet", "")
        whitelist = client_profile.whitelist_wallets if client_profile else []
        if dest_wallet and dest_wallet not in whitelist:
            mod = rules.score_modifiers.get("destination_is_new", 1.0)
            if mod != 1.0:
                adjusted *= mod
                modifiers_applied["destination_is_new"] = mod
                rules_triggered.append(
                    f"New destination wallet: score ×{mod}"
                )
        
        # Amount above EDD threshold
        amount = float(case_data.get("requested_amount_chf", 0))
        if amount >= rules.cdd.enhanced_due_diligence_threshold_chf:
            mod = rules.score_modifiers.get(
                "amount_above_eddrequires_threshold", 1.0
            )
            if mod != 1.0:
                adjusted *= mod
                modifiers_applied["amount_above_edd"] = mod
                rules_triggered.append(
                    f"Amount triggers EDD (CHF {rules.cdd.enhanced_due_diligence_threshold_chf:,.0f}): "
                    f"score ×{mod}"
                )
        
        # Cap at 100
        adjusted = min(adjusted, 100.0)
        
        # === Determine action using jurisdiction thresholds ===
        if adjusted <= rules.action_thresholds.allow_max:
            action = DecisionAction.ALLOW
        elif adjusted <= rules.action_thresholds.step_up_max:
            action = DecisionAction.STEP_UP_VERIFICATION
        elif adjusted <= rules.action_thresholds.escalate_max:
            action = DecisionAction.ESCALATE
        else:
            action = DecisionAction.BLOCK
        
        # === Build applicable rules list ===
        applicable_rules = []
        if amount >= rules.travel_rule.threshold_chf:
            applicable_rules.append(
                f"Travel Rule: full beneficiary data required "
                f"(threshold CHF {rules.travel_rule.threshold_chf:,.0f})"
            )
        if amount >= rules.cdd.enhanced_due_diligence_threshold_chf:
            applicable_rules.append(
                f"Enhanced Due Diligence required "
                f"(CHF {rules.cdd.enhanced_due_diligence_threshold_chf:,.0f}+)"
            )
        if rules.reporting.suspicious_activity_24h:
            applicable_rules.append("24-hour suspicious activity reporting")
        if action == DecisionAction.BLOCK and rules.reporting.fiu_threshold_chf:
            if amount >= rules.reporting.fiu_threshold_chf:
                applicable_rules.append(
                    f"FIU report required (amount ≥ CHF "
                    f"{rules.reporting.fiu_threshold_chf:,.0f})"
                )
        
        logger.info(
            "jurisdiction_adjusted",
            base=round(base_score, 2),
            adjusted=round(adjusted, 2),
            jurisdiction=jurisdiction.value,
            action=action.value,
        )
        
        return JurisdictionAdjustedScore(
            jurisdiction_code=jurisdiction.value,
            jurisdiction_name=rules.name,
            base_score=round(base_score, 2),
            adjusted_score=round(adjusted, 2),
            modifiers_applied=modifiers_applied,
            recommended_action=action.value,
            applicable_rules=applicable_rules,
            officer_notes=rules.officer_notes,
        )
    
    def compare_jurisdictions(
        self,
        case_id: UUID,
        base_score: float,
    ) -> dict[str, JurisdictionAdjustedScore]:
        """
        Show how a case would be scored under EACH jurisdiction.
        
        Demo killer feature:
        "Same case: FINMA blocks, SFC escalates, MiCA approves."
        """
        case = self.store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        client = self.store.get_client(case.client_id)
        
        return {
            j.value: self.adjust_score(base_score, j, case, client)
            for j in self.loaded_jurisdictions
        }


# Singleton
_service: JurisdictionService | None = None


def get_jurisdiction_service() -> JurisdictionService:
    """FastAPI dependency."""
    global _service
    if _service is None:
        _service = JurisdictionService()
    return _service


def reset_jurisdiction_service() -> None:
    """For tests."""
    global _service
    _service = None
