"""
Tests for the drift-engine decision path (customer_id instead of case_id).

Covers:
- POST /decisions with customer_id records a drift decision
- POST /decisions with ai_hint enables override detection
- Override without rationale is rejected (400)
- ai_hint alongside case_id is rejected (422)
- GET /decisions/customer/{id} returns decisions chronologically
- Validation: neither case_id nor customer_id → 422
- Validation: both case_id and customer_id → 422
- Audit event type is drift_decision_recorded
- Cross-path isolation: drift decisions don't bleed into case decision lists
- Override flag and rationale survive round-trip through the list endpoint
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.schemas.enums import DecisionAction

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

OFFICER = "test.officer@amina.ch"


@pytest.fixture
def cid() -> str:
    """Unique drift customer ID per test — prevents cross-test contamination."""
    return f"DRIFT-{uuid4().hex[:8]}"


async def post_drift_decision(
    client: AsyncClient,
    customer_id: str,
    action: DecisionAction | str = "escalate",
    rationale: str | None = None,
    ai_hint: DecisionAction | str | None = None,
):
    payload: dict = {
        "customer_id": customer_id,
        "action": action,
        "officer_id": OFFICER,
    }
    if rationale is not None:
        payload["rationale"] = rationale
    if ai_hint is not None:
        payload["ai_hint"] = ai_hint
    return await client.post("/api/v1/decisions", json=payload)


# ---------------------------------------------------------------------------
# Record drift decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decision_created(client: AsyncClient, cid: str) -> None:
    resp = await post_drift_decision(client, cid)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["customer_id"] == cid
    assert body["case_id"] is None
    assert body["action"] == "escalate"
    assert body["officer_id"] == OFFICER
    assert body["overrode_ai"] is False


@pytest.mark.asyncio
async def test_drift_decision_ai_hint_no_override(client: AsyncClient, cid: str) -> None:
    """ai_hint matches action → overrode_ai is False, no rationale needed."""
    resp = await post_drift_decision(client, cid, action="escalate", ai_hint="escalate")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["overrode_ai"] is False
    assert body["ai_recommended_action"] == "escalate"


@pytest.mark.asyncio
async def test_drift_decision_ai_hint_override_with_rationale(
    client: AsyncClient, cid: str
) -> None:
    """ai_hint differs from action + rationale provided → accepted."""
    resp = await post_drift_decision(
        client,
        cid,
        action="allow",
        ai_hint="escalate",
        rationale="Customer confirmed legitimate restructuring via KYC docs.",
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["overrode_ai"] is True
    assert body["ai_recommended_action"] == "escalate"
    assert body["action"] == "allow"
    assert "restructuring" in body["rationale"]


@pytest.mark.asyncio
async def test_drift_decision_override_without_rationale_rejected(
    client: AsyncClient, cid: str
) -> None:
    """Override without rationale must be rejected with 400."""
    resp = await post_drift_decision(client, cid, action="allow", ai_hint="escalate")
    assert resp.status_code == 400, resp.text
    assert "rationale" in resp.text.lower()


# ---------------------------------------------------------------------------
# List drift decisions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_customer_decisions_empty(client: AsyncClient, cid: str) -> None:
    resp = await client.get(f"/api/v1/decisions/customer/{cid}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_customer_decisions_chronological(
    client: AsyncClient, cid: str
) -> None:
    """Multiple decisions for the same customer are returned in creation order."""
    for action in ("escalate", "step_up_verification", "block"):
        r = await post_drift_decision(client, cid, action=action)
        assert r.status_code == 201, r.text

    resp = await client.get(f"/api/v1/decisions/customer/{cid}")
    assert resp.status_code == 200, resp.text
    assert [d["action"] for d in resp.json()] == [
        "escalate",
        "step_up_verification",
        "block",
    ]


@pytest.mark.asyncio
async def test_list_customer_decisions_isolated_by_customer(
    client: AsyncClient,
) -> None:
    """Decisions for one customer don't appear under another."""
    cid_a = f"DRIFT-{uuid4().hex[:8]}"
    cid_b = f"DRIFT-{uuid4().hex[:8]}"

    await post_drift_decision(client, cid_a)
    await post_drift_decision(client, cid_b)

    resp_a = await client.get(f"/api/v1/decisions/customer/{cid_a}")
    resp_b = await client.get(f"/api/v1/decisions/customer/{cid_b}")

    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1
    assert resp_a.json()[0]["customer_id"] == cid_a
    assert resp_b.json()[0]["customer_id"] == cid_b


@pytest.mark.asyncio
async def test_list_reflects_override_flag(client: AsyncClient, cid: str) -> None:
    """Override flag and rationale survive the round-trip through the list endpoint."""
    r = await post_drift_decision(
        client,
        cid,
        action="allow",
        ai_hint="escalate",
        rationale="Customer provided verified restructuring documents.",
    )
    assert r.status_code == 201, r.text

    resp = await client.get(f"/api/v1/decisions/customer/{cid}")
    assert resp.status_code == 200, resp.text
    item = resp.json()[0]
    assert item["overrode_ai"] is True
    assert item["ai_recommended_action"] == "escalate"
    assert "restructuring" in item["rationale"]


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_neither_case_nor_customer_id_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={"action": "allow", "officer_id": OFFICER},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_both_case_and_customer_id_rejected(
    client: AsyncClient, seed_case: dict, cid: str
) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={
            "case_id": seed_case["case_id"],
            "customer_id": cid,
            "action": "allow",
            "officer_id": OFFICER,
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_ai_hint_with_case_id_rejected(
    client: AsyncClient, seed_case: dict
) -> None:
    """ai_hint is only valid for the drift workflow; case path rejects it."""
    resp = await client.post(
        "/api/v1/decisions",
        json={
            "case_id": seed_case["case_id"],
            "action": "allow",
            "officer_id": OFFICER,
            "ai_hint": "escalate",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "ai_hint" in resp.text.lower()


@pytest.mark.asyncio
async def test_empty_customer_id_rejected(client: AsyncClient) -> None:
    """customer_id must be at least 1 character (min_length constraint)."""
    resp = await client.post(
        "/api/v1/decisions",
        json={"customer_id": "", "action": "allow", "officer_id": OFFICER},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Cross-path isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decisions_not_mixed_with_case_decisions(
    client: AsyncClient, cid: str, seed_case: dict
) -> None:
    """A drift decision for a customer does not appear in the case decision list."""
    r = await post_drift_decision(client, cid, action="escalate")
    assert r.status_code == 201, r.text

    case_resp = await client.get(
        f"/api/v1/decisions/case/{seed_case['case_id']}"
    )
    assert case_resp.status_code == 200
    assert case_resp.json() == []  # case has no decisions

    customer_resp = await client.get(f"/api/v1/decisions/customer/{cid}")
    item = customer_resp.json()[0]
    assert item["case_id"] is None
    assert item["customer_id"] == cid


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decision_audit_event(
    client: AsyncClient, cid: str, audit_query
) -> None:
    resp = await post_drift_decision(client, cid, action="block")
    assert resp.status_code == 201, resp.text

    entries = await audit_query("drift_decision_recorded")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.payload["customer_id"] == cid
    assert entry.payload["action"] == "block"
    assert entry.payload["overrode_ai"] is False
