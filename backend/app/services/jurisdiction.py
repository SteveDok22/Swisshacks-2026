"""
Jurisdiction Service — async DB version.

Loads YAML rules at startup (singleton), applies them per case.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.case import Case
from app.schemas.client import Client
from app.schemas.enums import DecisionAction, Jurisdiction
from app.schemas.jurisdiction import (
    JurisdictionAdjustedScore,
    JurisdictionRules,
)
from app.services.db_store import DbStore

logger = get_logger(__name__)


class JurisdictionService:
    """Loads and applies jurisdiction-specific rules."""
    
    # Class-level cache (YAML doesn't change at runtime)
    _rules_cache: dict[Jurisdiction, JurisdictionRules] = {}
    _loaded = False
    
    def __init__(
        self,
        session: AsyncSession | None = None,
        rules_dir: Path | None = None,
    ) -> None:
        self.session = session
        self.rules_dir = rules_dir or Path(settings.jurisdictions_dir)
        if not self._loaded:
            self._load_all()
    
    def _load_all(self) -> None:
        """Load all YAML files (cached class-level)."""
        cls = self.__class__
        for j in Jurisdiction:
            yaml_path = self.rules_dir / f"{j.value}.yaml"
            if not yaml_path.exists():
                logger.warning("jurisdiction_yaml_missing", code=j.value)
                continue
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                rules = JurisdictionRules(**data)
                cls._rules_cache[j] = rules
                logger.info("jurisdiction_loaded", code=j.value, regulator=rules.regulator)
            except Exception as e:
                logger.error("jurisdiction_load_failed", code=j.value, error=str(e))
        cls._loaded = True
    
    @property
    def loaded_jurisdictions(self) -> list[Jurisdiction]:
        return list(self._rules_cache.keys())
    
    def get_rules(self, jurisdiction: Jurisdiction) -> JurisdictionRules:
        if jurisdiction not in self._rules_cache:
            raise ValueError(f"No rules loaded for {jurisdiction}")
        return self._rules_cache[jurisdiction]
    
    def adjust_score(
        self,
        base_score: float,
        jurisdiction: Jurisdiction,
        case: Case,
        client: Client | None = None,
    ) -> JurisdictionAdjustedScore:
        """Apply jurisdiction-specific modifiers to a base ML score."""
        rules = self.get_rules(jurisdiction)
        
        adjusted = base_score
        modifiers_applied: dict[str, float] = {}
        rules_triggered: list[str] = []
        
        case_data = case.context.data
        client_profile = client.profile if client else None
        
        if client_profile and client_profile.is_pep:
            mod = rules.score_modifiers.get("client_is_pep", 1.0)
            if mod != 1.0:
                adjusted *= mod
                modifiers_applied["client_is_pep"] = mod
                rules_triggered.append(f"PEP client: score ×{mod}")
        
        dest_wallet = case_data.get("destination_wallet", "")
        whitelist = client_profile.whitelist_wallets if client_profile else []
        if dest_wallet and dest_wallet not in whitelist:
            mod = rules.score_modifiers.get("destination_is_new", 1.0)
            if mod != 1.0:
                adjusted *= mod
                modifiers_applied["destination_is_new"] = mod
                rules_triggered.append(f"New destination: score ×{mod}")
        
        amount = float(case_data.get("requested_amount_chf", 0))
        if amount >= rules.cdd.enhanced_due_diligence_threshold_chf:
            mod = rules.score_modifiers.get(
                "amount_above_eddrequires_threshold", 1.0
            )
            if mod != 1.0:
                adjusted *= mod
                modifiers_applied["amount_above_edd"] = mod
                rules_triggered.append(f"Amount triggers EDD: score ×{mod}")
        
        adjusted = min(adjusted, 100.0)
        
        if adjusted <= rules.action_thresholds.allow_max:
            action = DecisionAction.ALLOW
        elif adjusted <= rules.action_thresholds.step_up_max:
            action = DecisionAction.STEP_UP_VERIFICATION
        elif adjusted <= rules.action_thresholds.escalate_max:
            action = DecisionAction.ESCALATE
        else:
            action = DecisionAction.BLOCK
        
        applicable_rules = []
        if amount >= rules.travel_rule.threshold_chf:
            applicable_rules.append(
                f"Travel Rule (threshold CHF {rules.travel_rule.threshold_chf:,.0f})"
            )
        if amount >= rules.cdd.enhanced_due_diligence_threshold_chf:
            applicable_rules.append("Enhanced Due Diligence required")
        if rules.reporting.suspicious_activity_24h:
            applicable_rules.append("24-hour suspicious activity reporting")
        
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
    
    async def compare_jurisdictions(
        self,
        case_id: UUID,
        base_score: float,
    ) -> dict[str, JurisdictionAdjustedScore]:
        """Show how a case would be scored under EACH jurisdiction."""
        if self.session is None:
            raise RuntimeError("Session required for compare_jurisdictions")
        
        store = DbStore(self.session)
        case = await store.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        
        client = await store.get_client(case.client_id)
        
        return {
            j.value: self.adjust_score(base_score, j, case, client)
            for j in self.loaded_jurisdictions
        }
