"""
Integration tests: audit entries are written for every compliance-relevant event.

Covers the gaps identified in the audit coverage review:
  - counterfactuals_generated  (was never logged)
  - jurisdiction_compared      (was never logged)
  - data_exported              (was never logged)
  - explanation_generated on the stream path (was silently skipped)
  - actor_id captured on case events
  - count query returns correct totals when filters are active
  - case_status_updated payload includes old_status
  - decision_recorded payload includes jurisdiction
  - drift_rfi_generated payload includes actual question text

Each test:
  1. Seeds the DB with a client + case (via seed_case fixture where needed)
  2. Makes a real HTTP request via the test client
  3. Queries the test DB for the expected audit entry
  4. Asserts fields match what we documented

Fixtures: client, audit_query, seed_case  (all from conftest.py)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _first_drift_id(client: AsyncClient) -> str:
    resp = await client.get("/api/v1/drift/subjects")
    assert resp.status_code == 200
    customers = resp.json()
    assert customers, "Drift engine returned an empty book"
    return customers[0]["drift_id"]


# ---------------------------------------------------------------------------
# Events that were documented but never written
# ---------------------------------------------------------------------------

class TestPreviouslyMissingEvents:

    async def test_data_exported_written_on_history_fetch(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        resp = await client.get(f"/api/v1/cases/{case_id}/history")
        assert resp.status_code == 200

        entries = await audit_query("data_exported")
        assert len(entries) == 1, "data_exported must be written on every history fetch"

        entry = entries[0]
        assert str(entry.case_id) == case_id
        assert entry.payload["export_type"] == "case_audit_trail"
        assert "entries_exported" in entry.payload

    async def test_counterfactuals_generated_written(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        resp = await client.post(f"/api/v1/counterfactuals/{case_id}")
        # 200 even on graceful ML failure — the endpoint swallows exceptions
        assert resp.status_code == 200

        entries = await audit_query("counterfactuals_generated")
        assert len(entries) == 1, "counterfactuals_generated must be written"

        entry = entries[0]
        assert str(entry.case_id) == case_id
        assert "n_scenarios_requested" in entry.payload
        assert "scenarios_generated" in entry.payload

    async def test_jurisdiction_compared_written(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        resp = await client.post(f"/api/v1/jurisdictions/compare/{case_id}")
        assert resp.status_code == 200

        entries = await audit_query("jurisdiction_compared")
        assert len(entries) == 1, "jurisdiction_compared must be written"

        entry = entries[0]
        assert str(entry.case_id) == case_id
        assert "jurisdictions_compared" in entry.payload
        assert isinstance(entry.payload["jurisdictions_compared"], list)
        assert len(entry.payload["jurisdictions_compared"]) > 0
        assert "base_score" in entry.payload
        assert "adjusted_scores" in entry.payload
        assert entry.risk_score is not None

    async def test_explanation_generated_written_on_stream_path(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        # Stream endpoint — previously this logged nothing
        resp = await client.get(f"/api/v1/explanations/{case_id}/stream")
        # SSE response; 200 means the handler ran and the log was flushed
        assert resp.status_code == 200

        entries = await audit_query("explanation_generated")
        assert any(
            str(e.case_id) == case_id for e in entries
        ), "explanation_generated must be written on the stream path"

        stream_entries = [
            e for e in entries
            if str(e.case_id) == case_id and e.payload.get("llm_mode") == "stream"
        ]
        assert len(stream_entries) >= 1


# ---------------------------------------------------------------------------
# actor_id captured on case events
# ---------------------------------------------------------------------------

class TestCaseActorCapture:

    async def test_actor_id_on_case_created(self, client, audit_query, seed_case):
        client_id = seed_case["client_id"]

        resp = await client.post(
            "/api/v1/cases",
            json={
                "client_id": client_id,
                "case_type": "social_engineering",
                "jurisdiction": "CH",
                "context": {
                    "summary": "Actor capture test",
                    "data": {"requested_amount_chf": 1000},
                },
            },
            params={"actor_id": "anna.mueller"},
        )
        assert resp.status_code == 201

        entries = await audit_query("case_created")
        created = [e for e in entries if e.actor_id == "anna.mueller"]
        assert len(created) >= 1
        assert created[0].actor_type == "compliance_officer"

    async def test_no_actor_id_on_case_created_defaults_to_system(
        self, client, audit_query, seed_case
    ):
        client_id = seed_case["client_id"]

        await client.post(
            "/api/v1/cases",
            json={
                "client_id": client_id,
                "case_type": "social_engineering",
                "jurisdiction": "CH",
                "context": {"summary": "System actor test", "data": {}},
            },
        )

        entries = await audit_query("case_created")
        system_entries = [e for e in entries if e.actor_id is None]
        assert len(system_entries) >= 1
        assert system_entries[0].actor_type == "system"

    async def test_actor_id_on_status_update(self, client, audit_query, seed_case):
        case_id = seed_case["case_id"]

        resp = await client.patch(
            f"/api/v1/cases/{case_id}/status",
            params={"new_status": "in_review", "actor_id": "anna.mueller"},
        )
        assert resp.status_code == 200

        entries = await audit_query("case_status_updated")
        assert len(entries) == 1
        assert entries[0].actor_id == "anna.mueller"
        assert entries[0].actor_type == "compliance_officer"

    async def test_actor_id_on_data_exported(self, client, audit_query, seed_case):
        case_id = seed_case["case_id"]

        await client.get(
            f"/api/v1/cases/{case_id}/history",
            params={"actor_id": "anna.mueller"},
        )

        entries = await audit_query("data_exported")
        assert entries[0].actor_id == "anna.mueller"
        assert entries[0].actor_type == "compliance_officer"

    async def test_actor_id_on_scoring(self, client, audit_query, seed_case):
        case_id = seed_case["case_id"]

        resp = await client.post(
            f"/api/v1/scoring/{case_id}",
            params={"actor_id": "anna.mueller"},
        )
        assert resp.status_code == 200

        entries = await audit_query("case_scored")
        scored = [e for e in entries if e.actor_id == "anna.mueller"]
        assert len(scored) >= 1
        assert scored[0].actor_type == "compliance_officer"


# ---------------------------------------------------------------------------
# Payload completeness
# ---------------------------------------------------------------------------

class TestPayloadCompleteness:

    async def test_status_update_includes_old_status(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        resp = await client.patch(
            f"/api/v1/cases/{case_id}/status",
            params={"new_status": "in_review"},
        )
        assert resp.status_code == 200

        entries = await audit_query("case_status_updated")
        assert len(entries) == 1
        payload = entries[0].payload
        assert "old_status" in payload, "old_status must be logged for state transitions"
        assert "new_status" in payload
        assert payload["old_status"] == "pending"
        assert payload["new_status"] == "in_review"

    async def test_decision_payload_includes_jurisdiction(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        # Score first so the decision service can derive AI recommendation
        await client.post(f"/api/v1/scoring/{case_id}")

        resp = await client.post(
            "/api/v1/decisions",
            json={
                "case_id": case_id,
                "action": "allow",
                "officer_id": "anna.mueller",
            },
        )
        assert resp.status_code == 201

        entries = await audit_query("decision_recorded")
        assert len(entries) >= 1
        assert "jurisdiction" in entries[0].payload
        assert entries[0].payload["jurisdiction"] == "CH"

    async def test_rfi_payload_includes_question_text(self, client, audit_query):
        customers = (await client.get("/api/v1/drift/subjects")).json()
        drift_id = customers[0]["drift_id"]

        await client.post(f"/api/v1/drift/rfi/{drift_id}")

        entries = await audit_query("drift_rfi_generated")
        assert len(entries) == 1
        payload = entries[0].payload
        assert "questions" in payload, "Actual question text must be logged, not just count"
        assert isinstance(payload["questions"], list)
        assert len(payload["questions"]) >= 1
        # Every question must be a non-empty string
        for q in payload["questions"]:
            assert isinstance(q, str) and len(q) > 0

    async def test_jurisdiction_payload_has_adjusted_scores(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        await client.post(f"/api/v1/jurisdictions/compare/{case_id}")

        entries = await audit_query("jurisdiction_compared")
        payload = entries[0].payload
        assert "adjusted_scores" in payload
        # Each key is a jurisdiction code, each value is a float score
        for code, score in payload["adjusted_scores"].items():
            assert isinstance(code, str)
            assert isinstance(score, float | int)

    async def test_counterfactuals_payload_has_scenario_count(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        await client.post(f"/api/v1/counterfactuals/{case_id}?n_scenarios=2")

        entries = await audit_query("counterfactuals_generated")
        payload = entries[0].payload
        assert payload["n_scenarios_requested"] == 2
        assert "scenarios_generated" in payload


# ---------------------------------------------------------------------------
# Count query correctness
# ---------------------------------------------------------------------------

class TestAuditCountQueryCorrectness:

    async def test_count_reflects_actor_filter(self, client, audit_query):
        """
        The count returned by GET /audit must match the number of items
        when filtering by actor_id — not the unfiltered total.
        """
        drift_id = await _first_drift_id(client)

        # Two requests: one with actor, one without
        await client.get(
            f"/api/v1/drift/subjects/{drift_id}",
            params={"actor_id": "anna.mueller"},
        )
        await client.get(f"/api/v1/drift/subjects/{drift_id}")

        # Query the audit API with actor filter
        resp = await client.get(
            "/api/v1/audit",
            params={"event_type": "drift_subject_analyzed", "actor_id": "anna.mueller"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # The total must match the number of items on this page
        # (both are small here, well within one page)
        assert data["total"] == len(data["items"]), (
            f"Filtered total {data['total']} != items on page {len(data['items'])} — "
            "count query is not applying all active filters"
        )
        assert data["total"] == 1

    async def test_count_reflects_risk_level_filter(self, client):
        # Generate a scan (no specific risk level on scan event — use customer)
        drift_id = await _first_drift_id(client)
        await client.get(f"/api/v1/drift/subjects/{drift_id}")

        # Query for a risk level that may or may not have entries
        resp = await client.get(
            "/api/v1/audit",
            params={"risk_level": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Whatever the count says, items must match it
        assert data["total"] == len(data["items"])

    async def test_unfiltered_count_includes_all_events(self, client):
        drift_id = await _first_drift_id(client)
        await client.get(f"/api/v1/drift/subjects/{drift_id}")
        await client.post("/api/v1/drift/scan")

        resp = await client.get("/api/v1/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert data["total"] == len(data["items"])


# ---------------------------------------------------------------------------
# No double-logging on repeat calls
# ---------------------------------------------------------------------------

class TestNoExtraAuditEntries:

    async def test_data_exported_written_once_per_history_call(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        await client.get(f"/api/v1/cases/{case_id}/history")
        await client.get(f"/api/v1/cases/{case_id}/history")

        entries = await audit_query("data_exported")
        assert len(entries) == 2, "One data_exported entry per call, not more"

    async def test_counterfactuals_written_once_per_call(
        self, client, audit_query, seed_case
    ):
        case_id = seed_case["case_id"]

        await client.post(f"/api/v1/counterfactuals/{case_id}")
        await client.post(f"/api/v1/counterfactuals/{case_id}")

        entries = await audit_query("counterfactuals_generated")
        assert len(entries) == 2
