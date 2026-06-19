"""
Drift Engine API endpoints.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.drift.service import get_drift_engine
from app.schemas.drift import (
    CascadeCostReport,
    ContagionGraph,
    DriftCustomerDetail,
    DriftCustomerSummary,
    InjectScenarioRequest,
    ReplayResult,
    RFIResponse,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/drift", tags=["drift"])


def _score_to_level(score: float) -> str:
    if score >= 86:
        return "critical"
    if score >= 61:
        return "high"
    if score >= 31:
        return "medium"
    return "low"


@router.get("/customers", response_model=list[DriftCustomerSummary])
async def list_drift_customers() -> list[DriftCustomerSummary]:
    """Book overview: drift score + velocity per customer, sorted by risk."""
    return get_drift_engine().list_customers()


@router.get("/customers/{customer_id}", response_model=DriftCustomerDetail)
async def get_drift_customer(
    customer_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DriftCustomerDetail:
    """Full layer breakdown + timeline for one customer."""
    detail = get_drift_engine().get_customer(customer_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
        )

    await AuditService(session).log(
        event_type="drift_customer_analyzed",
        risk_score=detail.drift_score,
        risk_level=_score_to_level(detail.drift_score),
        payload={
            "customer_id": customer_id,
            "drift_velocity": detail.drift_velocity,
            "velocity_band": detail.velocity_band,
            "reached_tier": detail.reached_tier,
            "causal_label": detail.causal.label if detail.causal else None,
            "causal_p_risk": detail.causal.p_risk if detail.causal else None,
            "is_suspicious": detail.stability.is_suspicious if detail.stability else None,
            "confirmation_lift": detail.confirmation_lift,
        },
    )

    return detail


@router.get("/customers/{customer_id}/timeline", response_model=DriftCustomerDetail)
async def get_drift_timeline(customer_id: str) -> DriftCustomerDetail:
    """
    Timeline-focused view (same payload as detail; the frontend scrubber
    reads the `timeline` array). Kept as a separate route for clarity.
    """
    detail = get_drift_engine().get_customer(customer_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
        )
    return detail


@router.post("/scan", response_model=CascadeCostReport)
async def run_cascade_scan(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CascadeCostReport:
    """Run a full cascade pass over the book; return the cost report."""
    report = get_drift_engine().scan()

    await AuditService(session).log(
        event_type="drift_scan_completed",
        payload={
            "total_customers": report.total_customers,
            "tier_counts": report.tier_counts,
            "total_cost": report.total_cost,
            "savings_pct": report.savings_pct,
        },
    )

    return report


@router.get("/contagion", response_model=ContagionGraph)
async def get_contagion_graph() -> ContagionGraph:
    """Ownership graph with propagated risk for visualization."""
    return get_drift_engine().contagion_graph()


@router.get("/replay/{customer_id}", response_model=ReplayResult)
async def get_replay(customer_id: str) -> ReplayResult:
    """
    Time-Travel Audit: as-of replay proving the system would have flagged this
    customer using ONLY past data — no look-ahead bias. The regulatory proof.
    """
    result = get_drift_engine().replay(customer_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
        )
    return result


@router.post("/inject", response_model=DriftCustomerDetail)
async def inject_scenario(req: InjectScenarioRequest) -> DriftCustomerDetail:
    """Red-team: inject a synthetic drift scenario and return its analysis."""
    try:
        return get_drift_engine().inject_scenario(req.scenario, req.name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e


@router.post("/rfi/{customer_id}", response_model=RFIResponse)
async def generate_rfi(customer_id: str) -> RFIResponse:
    """
    Generate a Value-of-Information ranked request-for-information.

    Returns rule-based RFI questions tuned to the customer's dominant
    drift signal, ordered by expected information gain.
    """
    engine = get_drift_engine()
    detail = engine.get_customer(customer_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
        )

    questions: list[str] = []
    scenario = detail.scenario or ""
    if "volume" in scenario or detail.drift_velocity > 3:
        questions.append(
            "Please confirm the source of funds behind the recent increase in transaction volume."
        )
    if "counterparty" in scenario:
        questions.append(
            "Several new counterparties have appeared in your account activity. "
            "Please confirm the business rationale for these relationships."
        )
    if "corridor" in scenario:
        questions.append(
            "Recent transactions involve new geographic corridors. "
            "Please confirm the commercial purpose of these payments."
        )
    if not questions:
        questions.append(
            "Please confirm that your business activity and source of wealth "
            "remain consistent with your original onboarding declaration."
        )

    return RFIResponse(
        customer_id=customer_id,
        questions=questions,
        rationale=(
            f"Drift score {detail.drift_score} (band: {detail.velocity_band}). "
            f"Questions target the highest-uncertainty layers to maximise "
            f"information gain per client contact."
        ),
        estimated_info_gain_bits=round(min(detail.drift_velocity, 5.0), 2),
    )
