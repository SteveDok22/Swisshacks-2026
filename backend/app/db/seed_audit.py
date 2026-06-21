"""
Seed a realistic, backdated compliance **audit trail** for the demo.

Why: a KYC/AML product is judged on its compliance backbone, but the audit log
is empty on a fresh start (``seed.py`` writes only clients/cases/baselines). This
module fills it with a believable ~3-week trail so the Audit page is immediately
rich — named compliance officers triaging real drift subjects, nightly system
scans, decisions (some overriding the AI), RFIs, and case-management events.

Design:
- **Deterministic**: every timestamp is computed relative to ``now`` (no RNG), so
  the trail is the same shape on every startup. The DB is recreated each boot, so
  the seed reruns cleanly.
- **Audit-only**: NO ``DecisionDB`` rows are created — the DecisionBar stays empty
  so a live demo can record a decision itself. These are audit entries only.
- **Real references**: entries carry the real ``drift_id`` of book subjects and the
  real ``case_id``/``client_id`` of seeded cases, so cross-referencing + every
  filter (event type / risk / actor / customer / date range) works.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.db.models import AuditEntryDB, CaseDB

logger = get_logger(__name__)

# --- Compliance cast -------------------------------------------------------
_OFFICERS = ["anna.mueller", "marc.weber", "sophie.dubois"]  # compliance_officer
_RM = "t.brunner"  # relationship manager

# --- Curated flagged subjects (representative of the live engine output) ---
# (drift_id, name, score, level, velocity_band, reached_tier, causal_label)
_FLAGGED: list[tuple[str, str, float, str, str, str, str]] = [
    ("drift-011", "Castor Trade Finance AG", 99.7, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-003", "Alpine Logistics Group AG", 96.3, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-live-002", "Rosneft Trading S.A.", 90.0, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-010", "Säntis Import-Export AG", 92.8, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-001", "Helvetia Pharma Holding AG", 91.7, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-006", "Lattice Labs AG", 91.7, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-008", "Bernina Wealth Partners AG", 90.0, "critical", "notable", "T2_LLM", "risk"),
    ("drift-002", "Léman FX Trading SA", 87.5, "critical", "rapid", "T2_LLM", "risk"),
    ("drift-004", "Glarnisch Holding AG", 76.7, "high", "notable", "T1_ML", "risk"),
    ("drift-005", "HelvetiaX", 78.2, "high", "natural", "T2_LLM", "ambiguous"),
    ("drift-012", "Engadin Capital SA", 72.5, "high", "structural", "T2_LLM", "risk"),
    ("drift-live-004", "WW International, Inc.", 60.0, "medium", "notable", "T1_ML", "ambiguous"),
    ("drift-007", "Rhône Capital GmbH", 50.0, "medium", "natural", "T1_ML", "ambiguous"),
]

# Per-subject one-line officer rationale (compliance voice), keyed by drift_id.
_RATIONALE: dict[str, str] = {
    "drift-011": (
        "Confirmed structuring across four linked shells plus a new sanctioned "
        "UBO (Rosneft Trading S.A.). SAR filed with MROS (ref. 2026-MROS-04417); "
        "account frozen pending enhanced review."
    ),
    "drift-003": (
        "Sudden layering flows across affiliated entities, 1 hop from a flagged "
        "seed node. Escalated to Enhanced Due Diligence."
    ),
    "drift-live-002": (
        "Direct OFAC/EU sanctions match on the counterparty. Mandatory block and "
        "freeze; reported to compliance head."
    ),
    "drift-010": (
        "Dormant shell reactivated with a large inbound burst after 3 quiet years "
        "(Azerbaijani-Laundromat pattern). Source-of-funds requested."
    ),
    "drift-001": (
        "Sustained 12-month adverse-media spike consistent with a pre-collapse "
        "pattern. Escalated for EDD and management review."
    ),
    "drift-006": (
        "Public SaaS→ICO pivot corroborated by a website business-model shift. "
        "Re-assessed AML profile; escalated."
    ),
    "drift-008": (
        "New beneficial owner screens as a sanctioned entity. Mandatory re-KYC and "
        "escalation."
    ),
    "drift-002": (
        "Payment corridors drifted CH/DE→RU/AE with money-mule velocity. Stepped up "
        "verification and corridor controls."
    ),
    "drift-004": (
        "Legal-name change detected (shelf-cycling pattern). Re-KYC clock reset is "
        "suspicious; requested registry confirmation."
    ),
    "drift-005": (
        "Website pivot advisory→crypto-exchange. Requested updated business "
        "description and licensing status."
    ),
    "drift-012": (
        "Anomalously smooth book while peers move (suspicious stability). Flagged "
        "for manual transaction review."
    ),
    "drift-live-004": (
        "GLEIF records a legal-name change (Weight Watchers → WW). Re-KYC triggered; "
        "requested confirmation of continuity of control."
    ),
    "drift-007": (
        "Jurisdiction change CH→BVI triggers mandatory re-KYC under FINMA AMLA. "
        "Requested updated UBO declaration and source-of-funds."
    ),
}

# RFI question banks per drift_id (subset surfaced in the payload).
_RFI_QUESTIONS: dict[str, list[str]] = {
    "drift-011": [
        "Provide source-of-funds documentation for the CHF 4.2M inflow in month 11.",
        "Confirm the identity and ownership stake of the newly added beneficial owner.",
        "Explain the rationale for the corridor shift toward RU/AE counterparties.",
    ],
    "drift-003": [
        "List all entities under common control and their inter-company flows.",
        "Provide commercial rationale for the back-to-back transfers in months 9–11.",
    ],
    "drift-007": [
        "Provide the registry filing evidencing the jurisdiction change to BVI.",
        "Submit an updated UBO declaration reflecting the new legal form.",
    ],
    "drift-001": [
        "Comment on the recent adverse-media coverage and any internal investigation.",
        "Provide audited financials for the last two reporting periods.",
    ],
    "drift-005": [
        "Confirm whether the entity now operates a crypto-asset exchange.",
        "Provide the licence/registration covering the new business activity.",
    ],
}


def _ai_recommended(score: float, *, confidence: float = 0.8) -> str:
    """Mirror decision.py's AI-recommendation derivation for the audit payload."""
    if score <= 30:
        return "allow"
    if score <= 60:
        return "step_up_verification"
    if score <= 85:
        return "block" if confidence >= 0.85 else "escalate"
    return "block"


def _officer_action(level: str, idx: int) -> str:
    """A plausible officer action for a subject's risk level (varied, deterministic)."""
    if level == "critical":
        return "block" if idx % 3 == 0 else "escalate"
    if level == "high":
        return "escalate" if idx % 2 == 0 else "step_up_verification"
    if level == "medium":
        return "step_up_verification" if idx % 2 == 0 else "allow"
    return "allow"


def _entry(
    event_type: str,
    occurred_at: datetime,
    *,
    payload: dict[str, Any] | None = None,
    drift_id: str | None = None,
    case_id: Any = None,
    client_id: Any = None,
    actor_id: str | None = None,
    actor_type: str = "system",
    risk_score: float | None = None,
    risk_level: str | None = None,
) -> AuditEntryDB:
    """Construct one backdated audit entry (occurred_at set explicitly)."""
    return AuditEntryDB(
        event_type=event_type,
        payload=payload or {},
        drift_id=drift_id,
        case_id=case_id,
        client_id=client_id,
        actor_id=actor_id,
        actor_type=actor_type,
        risk_score=risk_score,
        risk_level=risk_level,
        occurred_at=occurred_at,
    )


async def seed_audit_log(session: AsyncSession) -> int:
    """Append a deterministic, backdated compliance audit trail. Returns the count."""
    now = datetime.now(UTC)

    def day(days_ago: int, hour: int, minute: int) -> datetime:
        d = (now - timedelta(days=days_ago)).date()
        return datetime(d.year, d.month, d.day, hour, minute, tzinfo=UTC)

    entries: list[AuditEntryDB] = []
    dec_seq = 4400  # human-readable decision id counter (DEC-2026-NNNN)

    # 1) Nightly system drift scans over the last 18 days (~02:00, slightly jittered).
    for d in range(1, 19):
        entries.append(
            _entry(
                "drift_scan_completed",
                day(d, 2, (d * 7) % 50),
                payload={
                    "total_customers": 20,
                    "tier_counts": {"T0_RULES": 4, "T1_ML": 4 - (d % 3), "T2_LLM": 12 + (d % 3)},
                    "total_cost": round(0.16 + (d % 5) * 0.01, 2),
                    "llm_on_everything_cost": 3.10,
                    "savings_pct": round(93.0 + (d % 6) * 0.4, 1),
                    "llm_call_counts": {"real": 12 + (d % 3), "cached": (d * 2) % 9},
                },
                actor_type="system",
            )
        )

    # 2) Per-subject analyses (system) — each flagged subject analysed twice as it
    #    escalates, then human triage (decisions + a few RFIs) by rotating officers.
    for i, (drift_id, name, score, level, band, tier, causal) in enumerate(_FLAGGED):
        officer = _OFFICERS[i % len(_OFFICERS)]
        first_seen = 16 - i  # earliest-flagged subjects appear first
        re_seen = max(2, first_seen - 4)

        for d_off, vel in ((first_seen, 0.41 + i * 0.02), (re_seen, 0.55 + i * 0.02)):
            entries.append(
                _entry(
                    "drift_subject_analyzed",
                    day(d_off, 8, (i * 13) % 55),
                    payload={
                        "drift_id": drift_id,
                        "name": name,
                        "drift_velocity": round(vel, 3),
                        "velocity_band": band,
                        "reached_tier": tier,
                        "causal_label": causal,
                        "causal_p_risk": round(0.5 + i * 0.03, 3),
                        "is_suspicious": level in ("critical", "high"),
                        "confirmation_lift": round(1.4 + i * 0.05, 2),
                    },
                    drift_id=drift_id,
                    actor_type="system",
                    risk_score=score,
                    risk_level=level,
                )
            )

        # RFI for the subjects we have a question bank for (officer → RM).
        if drift_id in _RFI_QUESTIONS:
            entries.append(
                _entry(
                    "drift_rfi_generated",
                    day(re_seen - 1, 10, (i * 11) % 55),
                    payload={
                        "drift_id": drift_id,
                        "name": name,
                        "rfi_questions": _RFI_QUESTIONS[drift_id],
                        "estimated_info_gain_bits": round(2.5 + i * 0.3, 1),
                        "addressed_to": _RM,
                    },
                    drift_id=drift_id,
                    actor_id=officer,
                    actor_type="compliance_officer",
                    risk_score=score,
                    risk_level=level,
                )
            )

        # Human decision on the subject (skip the lowest few to leave some open).
        if level in ("critical", "high", "medium"):
            ai_rec = _ai_recommended(score)
            action = _officer_action(level, i)
            dec_seq += 1
            entries.append(
                _entry(
                    "drift_decision_recorded",
                    day(max(1, re_seen - 2), 14, (i * 17) % 55),
                    payload={
                        "drift_id": drift_id,
                        "name": name,
                        "action": action,
                        "overrode_ai": action != ai_rec,
                        "ai_recommended_action": ai_rec,
                        "rationale": _RATIONALE.get(drift_id, "Reviewed per standard procedure."),
                        "decision_id": f"DEC-2026-{dec_seq}",
                        "analysis_snapshot": {
                            "drift_score": score,
                            "risk_level": level,
                            "reached_tier": tier,
                            "causal_label": causal,
                        },
                    },
                    drift_id=drift_id,
                    actor_id=officer,
                    actor_type="compliance_officer",
                    risk_score=score,
                    risk_level=level,
                )
            )

    # 3) Case-management trail on the seeded cases (system scoring + officer decisions).
    case_rows = (await session.execute(select(CaseDB).limit(14))).scalars().all()
    for j, case in enumerate(case_rows):
        officer = _OFFICERS[j % len(_OFFICERS)]
        score = case.risk_score if case.risk_score is not None else round(40 + (j * 7) % 55, 1)
        level = case.risk_level or ("high" if score >= 61 else "medium" if score >= 31 else "low")
        base_day = 15 - (j % 12)

        entries.append(
            _entry(
                "case_scored",
                day(base_day, 7, (j * 9) % 55),
                payload={
                    "model": "xgboost_social_engineering",
                    "model_version": "1.3.0",
                    "recommended_action": _ai_recommended(score),
                    "confidence": round(0.62 + (j % 7) * 0.05, 2),
                    "top_features": ["amount_vs_baseline", "channel_pressure_markers", "destination_risk"],
                },
                case_id=case.id,
                client_id=case.client_id,
                actor_type="system",
                risk_score=score,
                risk_level=level,
            )
        )

        # Officer explanation + decision on roughly every other case.
        if j % 2 == 0:
            entries.append(
                _entry(
                    "explanation_generated",
                    day(base_day, 9, (j * 12) % 55),
                    payload={
                        "llm_mode": "live",
                        "anonymization_applied": True,
                        "fields_redacted_count": 4,
                        "fields_bucketed_count": 2,
                        "had_counterfactuals": j % 4 == 0,
                    },
                    case_id=case.id,
                    client_id=case.client_id,
                    actor_id=officer,
                    actor_type="compliance_officer",
                    risk_score=score,
                    risk_level=level,
                )
            )
            ai_rec = _ai_recommended(score)
            action = "block" if level == "high" else "allow" if level == "low" else "step_up_verification"
            dec_seq += 1
            entries.append(
                _entry(
                    "decision_recorded",
                    day(max(1, base_day - 1), 15, (j * 14) % 55),
                    payload={
                        "action": action,
                        "overrode_ai": action != ai_rec,
                        "ai_recommended_action": ai_rec,
                        "rationale": "Reviewed transaction context and client history; action per FINMA AMLA.",
                        "decision_id": f"DEC-2026-{dec_seq}",
                        "jurisdiction": case.jurisdiction,
                    },
                    case_id=case.id,
                    client_id=case.client_id,
                    actor_id=officer,
                    actor_type="compliance_officer",
                    risk_score=score,
                    risk_level=level,
                )
            )
            entries.append(
                _entry(
                    "case_status_updated",
                    day(max(1, base_day - 1), 15, (j * 14) % 55 + 1),
                    payload={
                        "old_status": "in_review",
                        "new_status": "resolved" if action in ("allow", "block") else "in_review",
                    },
                    case_id=case.id,
                    client_id=case.client_id,
                    actor_id=officer,
                    actor_type="compliance_officer",
                    risk_score=score,
                    risk_level=level,
                )
            )

    for e in entries:
        session.add(e)

    logger.info("audit_log_seeded", count=len(entries))
    return len(entries)
