"""BDD step definitions for audit_compliance.feature.

Mixes async HTTP steps (for the audit-entry scenario) with a sync code-inspection
step (for the append-only scenario). Requires asyncio_mode = "auto".
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.services.audit import AuditService

scenarios("features/audit_compliance.feature")


@pytest.fixture
def context() -> dict:
    return {}


# ---------------------------------------------------------------------------
# Scenario: Customer drift analysis writes an audit entry
# ---------------------------------------------------------------------------


@given("the drift engine has customers")
def drift_engine_ready() -> None:
    # The drift engine loads the synthetic book at startup — no setup needed.
    pass


@when("an officer requests the full analysis for the top customer")
async def get_top_customer_analysis(client: AsyncClient, context: dict) -> None:
    # Fetch the ranked customer list, then request the full detail for #1.
    list_resp = await client.get("/api/v1/drift/customers")
    assert list_resp.status_code == 200, list_resp.text
    customers = list_resp.json()
    assert customers, "Drift engine returned no customers"
    context["customer_id"] = customers[0]["customer_id"]
    detail_resp = await client.get(f"/api/v1/drift/customers/{context['customer_id']}")
    assert detail_resp.status_code == 200, detail_resp.text


@then(parsers.parse('an audit entry with event_type "{event_type}" exists'))
async def assert_audit_entry_exists(
    event_type: str, audit_query: Callable, context: dict
) -> None:
    entries = await audit_query(event_type=event_type)
    assert entries, (
        f"No audit entry with event_type={event_type!r} found after requesting "
        f"customer {context.get('customer_id')!r}"
    )
    context["audit_entry"] = entries[0]


@then("the audit entry contains a risk_score")
def assert_audit_has_risk_score(context: dict) -> None:
    entry = context["audit_entry"]
    assert entry.risk_score is not None, (
        f"Audit entry risk_score is None. Full entry: {entry}"
    )


# ---------------------------------------------------------------------------
# Scenario: Audit log is append-only by design
# ---------------------------------------------------------------------------


@when("I inspect the AuditService interface")
def inspect_audit_service_interface(context: dict) -> None:
    context["service_cls"] = AuditService


@then(parsers.parse('no "{method_name}" method exists on AuditService'))
def assert_no_destructive_method(method_name: str, context: dict) -> None:
    cls = context["service_cls"]
    assert not hasattr(cls, method_name), (
        f"AuditService must be append-only, but found a {method_name!r} method. "
        "Audit logs cannot be mutated — this is a compliance violation."
    )
