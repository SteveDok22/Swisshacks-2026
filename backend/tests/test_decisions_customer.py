"""
Tests for the drift-engine decision path (customer_id instead of case_id).

Covers:
- POST /decisions with customer_id records a drift decision
- POST /decisions with ai_hint enables override detection
- Override without rationale is rejected (400)
- GET /decisions/customer/{id} returns decisions chronologically
- Validation: neither case_id nor customer_id → 422
- Validation: both case_id and customer_id → 422
- Audit event type is drift_decision_recorded
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OFFICER = "test.officer@amina.ch"
CUSTOMER = "DRIFT-C001"


async def post_drift_decision(
    client: AsyncClient,
    customer_id: str = CUSTOMER,
    action: str = "escalate",
    rationale: str | None = None,
    ai_hint: str | None = None,
) -> dict:
    payload: dict = {
        "customer_id": customer_id,
        "action": action,
        "officer_id": OFFICER,
    }
    if rationale is not None:
        payload["rationale"] = rationale
    if ai_hint is not None:
        payload["ai_hint"] = ai_hint
    resp = await client.post("/api/v1/decisions", json=payload)
    return resp


# ---------------------------------------------------------------------------
# Record drift decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decision_created(client: AsyncClient) -> None:
    resp = await post_drift_decision(client)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["customer_id"] == CUSTOMER
    assert body["case_id"] is None
    assert body["action"] == "escalate"
    assert body["officer_id"] == OFFICER
    assert body["overrode_ai"] is False


@pytest.mark.asyncio
async def test_drift_decision_ai_hint_no_override(client: AsyncClient) -> None:
    """ai_hint matches action → overrode_ai is False, no rationale needed."""
    resp = await post_drift_decision(
        client, action="escalate", ai_hint="escalate"
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["overrode_ai"] is False
    assert body["ai_recommended_action"] == "escalate"


@pytest.mark.asyncio
async def test_drift_decision_ai_hint_override_with_rationale(
    client: AsyncClient,
) -> None:
    """ai_hint differs from action + rationale provided → accepted."""
    resp = await post_drift_decision(
        client,
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
    client: AsyncClient,
) -> None:
    """Override without rationale must be rejected with 400."""
    resp = await post_drift_decision(
        client, action="allow", ai_hint="escalate"
    )
    assert resp.status_code == 400, resp.text
    assert "rationale" in resp.text.lower()


# ---------------------------------------------------------------------------
# List drift decisions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_customer_decisions_empty(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/decisions/customer/{CUSTOMER}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_customer_decisions_chronological(client: AsyncClient) -> None:
    """Multiple decisions are returned in creation order."""
    for action in ("escalate", "step_up_verification", "block"):
        r = await post_drift_decision(client, action=action)
        assert r.status_code == 201, r.text

    resp = await client.get(f"/api/v1/decisions/customer/{CUSTOMER}")
    assert resp.status_code == 200, resp.text
    actions = [d["action"] for d in resp.json()]
    assert actions == ["escalate", "step_up_verification", "block"]


@pytest.mark.asyncio
async def test_list_customer_decisions_isolated_by_customer(
    client: AsyncClient,
) -> None:
    """Decisions for one customer don't appear under another."""
    await post_drift_decision(client, customer_id="DRIFT-A")
    await post_drift_decision(client, customer_id="DRIFT-B")

    resp_a = await client.get("/api/v1/decisions/customer/DRIFT-A")
    resp_b = await client.get("/api/v1/decisions/customer/DRIFT-B")

    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1
    assert resp_a.json()[0]["customer_id"] == "DRIFT-A"
    assert resp_b.json()[0]["customer_id"] == "DRIFT-B"


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
    client: AsyncClient, seed_case: dict
) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={
            "case_id": seed_case["case_id"],
            "customer_id": CUSTOMER,
            "action": "allow",
            "officer_id": OFFICER,
        },
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decision_audit_event(
    client: AsyncClient, audit_query
) -> None:
    resp = await post_drift_decision(client, action="block")
    assert resp.status_code == 201, resp.text

    entries = await audit_query("drift_decision_recorded")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.payload["customer_id"] == CUSTOMER
    assert entry.payload["action"] == "block"
    assert entry.payload["overrode_ai"] is False
