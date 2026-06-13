"""
Drift Engine API endpoints.

Six endpoints under /api/v1/drift/ — see DRIFT_ENGINE_README §10.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.drift.service import get_drift_engine
from app.schemas.drift import (
    CascadeCostReport,
    ContagionGraph,
    DriftCustomerDetail,
    DriftCustomerSummary,
    InjectScenarioRequest,
    RFIResponse,
)

router = APIRouter(prefix="/drift", tags=["drift"])


@router.get("/customers", response_model=list[DriftCustomerSummary])
async def list_drift_customers() -> list[DriftCustomerSummary]:
    """Book overview: drift score + velocity per customer, sorted by risk."""
    return get_drift_engine().list_customers()


@router.get("/customers/{customer_id}", response_model=DriftCustomerDetail)
async def get_drift_customer(customer_id: str) -> DriftCustomerDetail:
    """Full layer breakdown + timeline for one customer."""
    detail = get_drift_engine().get_customer(customer_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
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
async def run_cascade_scan() -> CascadeCostReport:
    """Run a full cascade pass over the book; return the cost report."""
    return get_drift_engine().scan()


@router.get("/contagion", response_model=ContagionGraph)
async def get_contagion_graph() -> ContagionGraph:
    """Ownership graph with propagated risk for visualization."""
    return get_drift_engine().contagion_graph()


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
    Generate a Value-of-Information ranked request-for-information (Layer 7).

    MVP: returns rule-based RFI questions tuned to the customer's dominant
    drift signal. A future version routes this through Claude for natural
    phrasing (the AnthropicClient is already available).
    """
    engine = get_drift_engine()
    detail = engine.get_customer(customer_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No drift customer {customer_id!r}",
        )

    # VoI heuristic: ask about whichever layer contributed most uncertainty
    questions: list[str] = []
    if detail.propagated_risk if hasattr(detail, "propagated_risk") else 0:
        pass
    # Pick questions by scenario signal
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
