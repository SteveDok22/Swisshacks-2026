"""
Integration tests: audit entries are written for all compliance-relevant drift endpoints.

Each test:
  1. Makes a real HTTP request via httpx.AsyncClient → FastAPI → drift engine
  2. Queries the in-memory test DB directly for the expected audit entry
  3. Asserts the entry fields match what the endpoint documented

Fixtures (from conftest.py):
  client       — AsyncClient wired to in-memory SQLite via get_session override
  audit_query  — async callable that queries AuditEntryDB from the same DB
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.enums import RiskLevel


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _first_customer_id(client: AsyncClient) -> str:
    """Return the customer_id of the highest-risk customer in the synthetic book."""
    response = await client.get("/api/v1/drift/customers")
    assert response.status_code == 200, response.text
    customers = response.json()
    assert customers, "Drift engine returned an empty book — check simulator.py"
    return customers[0]["customer_id"]


_VALID_RISK_LEVELS = {r.value for r in RiskLevel}


# ---------------------------------------------------------------------------
# Audit entry written tests
# ---------------------------------------------------------------------------

class TestAuditDriftEndpoints:

    async def test_customer_detail_writes_audit_entry(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        response = await client.get(f"/api/v1/drift/customers/{customer_id}")
        assert response.status_code == 200

        entries = await audit_query("drift_customer_analyzed")
        assert len(entries) == 1, "Expected exactly one audit entry"

        entry = entries[0]
        assert entry.event_type == "drift_customer_analyzed"
        assert entry.risk_score is not None
        assert entry.risk_level in _VALID_RISK_LEVELS
        assert entry.payload["customer_id"] == customer_id
        assert "drift_velocity" in entry.payload
        assert "velocity_band" in entry.payload
        assert "reached_tier" in entry.payload

    async def test_cascade_scan_writes_audit_entry(self, client, audit_query):
        response = await client.post("/api/v1/drift/scan")
        assert response.status_code == 200

        entries = await audit_query("drift_scan_completed")
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == "drift_scan_completed"
        assert entry.risk_score is None   # scan covers the whole book, no single score
        assert entry.risk_level is None
        assert "total_customers" in entry.payload
        assert "savings_pct" in entry.payload
        assert "tier_counts" in entry.payload
        assert "actual_t2_llm_calls" in entry.payload
        assert "real_t2_llm_calls" in entry.payload
        assert "mock_t2_llm_calls" in entry.payload
        assert entry.payload["total_customers"] > 0

    async def test_rfi_writes_audit_entry(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        response = await client.post(f"/api/v1/drift/rfi/{customer_id}")
        assert response.status_code == 200

        entries = await audit_query("drift_rfi_generated")
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == "drift_rfi_generated"
        assert entry.risk_score is not None
        assert entry.risk_level in _VALID_RISK_LEVELS
        assert entry.payload["customer_id"] == customer_id
        assert "question_count" in entry.payload
        assert entry.payload["question_count"] >= 1
        assert "estimated_info_gain_bits" in entry.payload
        # Questions text must be present — not just the count
        assert "questions" in entry.payload
        assert isinstance(entry.payload["questions"], list)
        assert len(entry.payload["questions"]) == entry.payload["question_count"]

    async def test_replay_writes_audit_entry(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        response = await client.get(f"/api/v1/drift/replay/{customer_id}")
        assert response.status_code == 200

        entries = await audit_query("drift_replay_executed")
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == "drift_replay_executed"
        assert entry.payload["customer_id"] == customer_id
        assert "lead_time_months" in entry.payload
        assert "alert_month" in entry.payload
        assert "alert_threshold" in entry.payload

    async def test_inject_writes_audit_entry(self, client, audit_query):
        response = await client.post(
            "/api/v1/drift/inject",
            json={"scenario": "volume_creep", "name": "Audit Test Customer"},
        )
        assert response.status_code == 200

        entries = await audit_query("drift_scenario_injected")
        assert len(entries) == 1

        entry = entries[0]
        assert entry.event_type == "drift_scenario_injected"
        assert entry.risk_score is not None
        assert entry.risk_level in _VALID_RISK_LEVELS
        assert entry.payload["scenario"] == "volume_creep"
        assert entry.payload["name"] == "Audit Test Customer"
        assert "reached_tier" in entry.payload


# ---------------------------------------------------------------------------
# actor_id capture
# ---------------------------------------------------------------------------

class TestDriftActorCapture:

    async def test_actor_id_captured_on_customer_detail(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        await client.get(
            f"/api/v1/drift/customers/{customer_id}",
            params={"actor_id": "anna.mueller"},
        )

        entries = await audit_query("drift_customer_analyzed")
        assert entries[0].actor_id == "anna.mueller"
        assert entries[0].actor_type == "compliance_officer"

    async def test_no_actor_id_defaults_to_system(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        await client.get(f"/api/v1/drift/customers/{customer_id}")

        entries = await audit_query("drift_customer_analyzed")
        assert entries[0].actor_id is None
        assert entries[0].actor_type == "system"

    async def test_actor_id_captured_on_scan(self, client, audit_query):
        await client.post("/api/v1/drift/scan", params={"actor_id": "anna.mueller"})

        entries = await audit_query("drift_scan_completed")
        assert entries[0].actor_id == "anna.mueller"
        assert entries[0].actor_type == "compliance_officer"

    async def test_actor_id_captured_on_replay(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        await client.get(
            f"/api/v1/drift/replay/{customer_id}",
            params={"actor_id": "anna.mueller"},
        )

        entries = await audit_query("drift_replay_executed")
        assert entries[0].actor_id == "anna.mueller"

    async def test_actor_id_captured_on_rfi(self, client, audit_query):
        customer_id = await _first_customer_id(client)

        await client.post(
            f"/api/v1/drift/rfi/{customer_id}",
            params={"actor_id": "anna.mueller"},
        )

        entries = await audit_query("drift_rfi_generated")
        assert entries[0].actor_id == "anna.mueller"

    async def test_actor_id_captured_on_inject(self, client, audit_query):
        await client.post(
            "/api/v1/drift/inject",
            json={"scenario": "volume_creep", "name": "Actor Test Customer"},
            params={"actor_id": "anna.mueller"},
        )

        entries = await audit_query("drift_scenario_injected")
        assert entries[0].actor_id == "anna.mueller"


# ---------------------------------------------------------------------------
# No audit on error paths
# ---------------------------------------------------------------------------

class TestAuditNotWrittenOnError:

    async def test_404_customer_detail_writes_no_audit(self, client, audit_query):
        response = await client.get("/api/v1/drift/customers/nonexistent-id-xyz")
        assert response.status_code == 404

        entries = await audit_query("drift_customer_analyzed")
        assert len(entries) == 0, "Audit must not be written for failed requests"

    async def test_404_replay_writes_no_audit(self, client, audit_query):
        response = await client.get("/api/v1/drift/replay/nonexistent-id-xyz")
        assert response.status_code == 404

        entries = await audit_query("drift_replay_executed")
        assert len(entries) == 0

    async def test_400_inject_invalid_scenario_writes_no_audit(self, client, audit_query):
        response = await client.post(
            "/api/v1/drift/inject",
            json={"scenario": "this_scenario_does_not_exist"},
        )
        assert response.status_code == 400

        entries = await audit_query("drift_scenario_injected")
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Scoring boundary regression (PR test plan item 6)
# ---------------------------------------------------------------------------

class TestAuditRiskLevelConsistency:

    async def test_risk_level_in_audit_is_consistent_with_score(self, client, audit_query):
        """
        Regression for the score_to_level boundary fix.
        Whatever score the drift engine produces, the risk_level stored in the
        audit log must match the corrected (<31 / <61 / <86) thresholds.
        """
        customer_id = await _first_customer_id(client)
        await client.get(f"/api/v1/drift/customers/{customer_id}")

        entries = await audit_query("drift_customer_analyzed")
        assert entries

        entry = entries[0]
        score = entry.risk_score
        level = entry.risk_level

        assert score is not None
        if score < 31:
            assert level == RiskLevel.LOW.value, f"score={score} should be low, got {level}"
        elif score < 61:
            assert level == RiskLevel.MEDIUM.value, f"score={score} should be medium, got {level}"
        elif score < 86:
            assert level == RiskLevel.HIGH.value, f"score={score} should be high, got {level}"
        else:
            assert level == RiskLevel.CRITICAL.value, f"score={score} should be critical, got {level}"

    async def test_all_customers_have_consistent_audit_levels(self, client, audit_query):
        """
        Call detail for every customer in the book and verify each audit entry's
        risk_level is consistent with its risk_score. Covers all score ranges.
        """
        response = await client.get("/api/v1/drift/customers")
        customers = response.json()

        for customer in customers:
            await client.get(f"/api/v1/drift/customers/{customer['customer_id']}")

        entries = await audit_query("drift_customer_analyzed")
        assert len(entries) == len(customers)

        for entry in entries:
            score = entry.risk_score
            level = entry.risk_level
            if score < 31:
                expected = RiskLevel.LOW.value
            elif score < 61:
                expected = RiskLevel.MEDIUM.value
            elif score < 86:
                expected = RiskLevel.HIGH.value
            else:
                expected = RiskLevel.CRITICAL.value
            assert level == expected, (
                f"customer={entry.payload.get('customer_id')}: "
                f"score={score} → expected {expected}, got {level}"
            )
