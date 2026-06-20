"""
Tests for the drift-engine decision path (drift_id instead of case_id).

Covers:
- POST /decisions with drift_id records a drift decision
- Override detection uses the server-derived recommendation
- Override without rationale is rejected (400)
- GET /decisions/subject/{id} returns decisions chronologically
- Validation: neither case_id nor drift_id → 422
- Validation: both case_id and drift_id → 422
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
async def drift_subject(client: AsyncClient) -> dict:
    """Use a real server-side drift customer with an escalation recommendation."""
    customers = (await client.get("/api/v1/drift/subjects")).json()
    for customer in customers:
        detail = (
            await client.get(f"/api/v1/drift/subjects/{customer['drift_id']}")
        ).json()
        if detail["recommended_action"] == "escalate":
            return detail
    raise AssertionError("Expected at least one drift customer recommended for escalation")


@pytest.fixture
def cid(drift_subject: dict) -> str:
    return drift_subject["drift_id"]


async def post_drift_decision(
    client: AsyncClient,
    drift_id: str,
    action: DecisionAction | str = "escalate",
    rationale: str | None = None,
):
    payload: dict = {
        "drift_id": drift_id,
        "action": action,
        "officer_id": OFFICER,
    }
    if rationale is not None:
        payload["rationale"] = rationale
    return await client.post("/api/v1/decisions", json=payload)


# ---------------------------------------------------------------------------
# Record drift decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decision_created(client: AsyncClient, cid: str) -> None:
    resp = await post_drift_decision(client, cid)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["drift_id"] == cid
    assert body["case_id"] is None
    assert body["action"] == "escalate"
    assert body["officer_id"] == OFFICER
    assert body["overrode_ai"] is False


@pytest.mark.asyncio
async def test_drift_decision_server_recommendation_no_override(
    client: AsyncClient, cid: str
) -> None:
    """Matching the server recommendation is not an override."""
    resp = await post_drift_decision(client, cid, action="escalate")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["overrode_ai"] is False
    assert body["ai_recommended_action"] == "escalate"


@pytest.mark.asyncio
async def test_drift_decision_override_with_rationale(
    client: AsyncClient, cid: str
) -> None:
    """Action differs from server recommendation + rationale → accepted."""
    resp = await post_drift_decision(
        client,
        cid,
        action="allow",
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
    resp = await post_drift_decision(client, cid, action="allow")
    assert resp.status_code == 400, resp.text
    assert "rationale" in resp.text.lower()


# ---------------------------------------------------------------------------
# List drift decisions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_subject_decisions_empty(client: AsyncClient, cid: str) -> None:
    resp = await client.get(f"/api/v1/decisions/subject/{cid}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_unknown_customer_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/decisions/subject/unknown-customer")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_list_subject_decisions_chronological(
    client: AsyncClient, cid: str
) -> None:
    """Multiple decisions for the same customer are returned in creation order."""
    for action in ("escalate", "step_up_verification", "block"):
        rationale = None if action == "escalate" else "Documented officer override."
        r = await post_drift_decision(
            client, cid, action=action, rationale=rationale
        )
        assert r.status_code == 201, r.text

    resp = await client.get(f"/api/v1/decisions/subject/{cid}")
    assert resp.status_code == 200, resp.text
    assert [d["action"] for d in resp.json()] == [
        "escalate",
        "step_up_verification",
        "block",
    ]


@pytest.mark.asyncio
async def test_list_subject_decisions_isolated_by_subject(
    client: AsyncClient, cid: str
) -> None:
    """Decisions for one customer don't appear under another."""
    customers = (await client.get("/api/v1/drift/subjects")).json()
    cid_a = cid
    cid_b = next(c["drift_id"] for c in customers if c["drift_id"] != cid_a)
    detail_b = (await client.get(f"/api/v1/drift/subjects/{cid_b}")).json()

    await post_drift_decision(client, cid_a)
    await post_drift_decision(
        client,
        cid_b,
        action=detail_b["recommended_action"],
    )

    resp_a = await client.get(f"/api/v1/decisions/subject/{cid_a}")
    resp_b = await client.get(f"/api/v1/decisions/subject/{cid_b}")

    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1
    assert resp_a.json()[0]["drift_id"] == cid_a
    assert resp_b.json()[0]["drift_id"] == cid_b


@pytest.mark.asyncio
async def test_list_reflects_override_flag(client: AsyncClient, cid: str) -> None:
    """Override flag and rationale survive the round-trip through the list endpoint."""
    r = await post_drift_decision(
        client,
        cid,
        action="allow",
        rationale="Customer provided verified restructuring documents.",
    )
    assert r.status_code == 201, r.text

    resp = await client.get(f"/api/v1/decisions/subject/{cid}")
    assert resp.status_code == 200, resp.text
    item = resp.json()[0]
    assert item["overrode_ai"] is True
    assert item["ai_recommended_action"] == "escalate"
    assert "restructuring" in item["rationale"]


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_neither_case_nor_drift_id_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={"action": "allow", "officer_id": OFFICER},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_both_case_and_drift_id_rejected(
    client: AsyncClient, seed_case: dict, cid: str
) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={
            "case_id": seed_case["case_id"],
            "drift_id": cid,
            "action": "allow",
            "officer_id": OFFICER,
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_unknown_decision_field_rejected(
    client: AsyncClient, seed_case: dict
) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={
            "case_id": seed_case["case_id"],
            "action": "allow",
            "officer_id": OFFICER,
            "unexpected_field": "escalate",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "unexpected_field" in resp.text.lower()


@pytest.mark.asyncio
async def test_empty_drift_id_rejected(client: AsyncClient) -> None:
    """drift_id must be at least 1 character (min_length constraint)."""
    resp = await client.post(
        "/api/v1/decisions",
        json={"drift_id": "", "action": "allow", "officer_id": OFFICER},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_unknown_customer_rejected(client: AsyncClient) -> None:
    resp = await post_drift_decision(
        client,
        f"UNKNOWN-{uuid4().hex}",
        action="allow",
    )
    assert resp.status_code == 400, resp.text
    assert "not found" in resp.text.lower()


@pytest.mark.asyncio
async def test_deprecated_ai_hint_rejected(client: AsyncClient, cid: str) -> None:
    resp = await client.post(
        "/api/v1/decisions",
        json={
            "drift_id": cid,
            "action": "allow",
            "officer_id": OFFICER,
            "rationale": "Attempted stale recommendation submission.",
            "ai_hint": "allow",
        },
    )
    assert resp.status_code == 422, resp.text
    assert "ai_hint" in resp.text


@pytest.mark.asyncio
async def test_short_override_rationale_rejected(
    client: AsyncClient, cid: str
) -> None:
    resp = await post_drift_decision(
        client,
        cid,
        action="allow",
        rationale="too short",
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

    customer_resp = await client.get(f"/api/v1/decisions/subject/{cid}")
    item = customer_resp.json()[0]
    assert item["case_id"] is None
    assert item["drift_id"] == cid


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_decision_audit_event(
    client: AsyncClient, cid: str, audit_query
) -> None:
    resp = await post_drift_decision(
        client,
        cid,
        action="block",
        rationale="Risk warrants immediate blocking action.",
    )
    assert resp.status_code == 201, resp.text

    entries = await audit_query("drift_decision_recorded")
    assert len(entries) == 1
    entry = entries[0]
    assert entry.payload["drift_id"] == cid
    assert entry.payload["action"] == "block"
    assert entry.drift_id == cid
    assert entry.risk_score is not None
    assert entry.payload["analysis_snapshot"]["analysis_version"] == "drift-v1"

    audit_resp = await client.get(
        "/api/v1/audit",
        params={
            "event_type": "drift_decision_recorded",
            "drift_id": cid,
        },
    )
    assert audit_resp.status_code == 200, audit_resp.text
    assert audit_resp.json()["total"] == 1
    assert audit_resp.json()["items"][0]["drift_id"] == cid
