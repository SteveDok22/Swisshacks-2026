"""BDD step definitions for api_contract.feature.

Uses the async `client` fixture from conftest.py (in-memory SQLite, ASGI transport).
Requires pytest-bdd >= 7.0 and asyncio_mode = "auto" (already set in pyproject.toml).
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from pytest_bdd import parsers, scenarios, then, when

scenarios("features/api_contract.feature")


@pytest.fixture
def context() -> dict:
    return {}


@when(parsers.parse('I call GET "{url}"'))
def call_get(url: str, client: AsyncClient, context: dict) -> None:
    context["response"] = asyncio.run(client.get(url))


@when(parsers.parse('I call POST "{url}"'))
def call_post(url: str, client: AsyncClient, context: dict) -> None:
    context["response"] = asyncio.run(client.post(url))


@then(parsers.parse("the response status is {status:d}"))
def assert_response_status(status: int, context: dict) -> None:
    actual = context["response"].status_code
    assert actual == status, (
        f"Expected HTTP {status} but got {actual}. Body: {context['response'].text[:200]}"
    )


@then("subjects are sorted by drift_score descending")
def assert_subjects_sorted(context: dict) -> None:
    subjects = context["response"].json()
    scores = [s["drift_score"] for s in subjects]
    assert scores == sorted(scores, reverse=True), (
        f"Subjects are not sorted by drift_score descending: {scores}"
    )


@then(parsers.parse('the response body contains "{key}"'))
def assert_body_contains_key(key: str, context: dict) -> None:
    data = context["response"].json()
    assert key in data, (
        f"Key {key!r} not found in response. Available keys: {list(data.keys())}"
    )


# --------------------------------------------------------------------------- #
# UC5 — DriftSubjectDetail exposes the ubo_screening field (contract test)     #
# --------------------------------------------------------------------------- #

async def test_subject_detail_exposes_ubo_screening(client: AsyncClient) -> None:
    """DriftSubjectDetail must always carry the ``ubo_screening`` list (UC5).

    Offline (default), no OpenSanctions hits are produced, so the field is an
    empty list — but it must be present and correctly typed in the contract.
    """
    listing = await client.get("/api/v1/drift/subjects")
    assert listing.status_code == 200
    subjects = listing.json()
    assert subjects, "synthetic book should not be empty"

    drift_id = subjects[0]["drift_id"]
    detail = await client.get(f"/api/v1/drift/subjects/{drift_id}")
    assert detail.status_code == 200

    body = detail.json()
    assert "ubo_screening" in body, (
        f"ubo_screening missing from detail. Keys: {list(body.keys())}"
    )
    assert isinstance(body["ubo_screening"], list)


# --------------------------------------------------------------------------- #
# UC10 — PublicSignalOut exposes the corroborated-critical pivot flag          #
# --------------------------------------------------------------------------- #

def test_public_signal_out_exposes_corroborated_flag() -> None:
    """A corroborated pivot's ``corroborated`` flag must survive the exact
    serialization path the service uses (``PublicSignalOut(**signal.to_dict())``,
    drift/service.py), so the signal card can give it a critical treatment (UC10).
    """
    from app.schemas.drift import PublicSignalOut
    from app.sources.base import PublicSignal

    corroborated = PublicSignal(
        month=9,
        signal_type="business_model_change",
        headline="Website content shifted materially since onboarding",
        severity=0.95,
        source="website-comparison",
        corroborated=True,
    )
    out = PublicSignalOut(**corroborated.to_dict())
    assert out.corroborated is True

    # The default (uncorroborated single signal) must stay False, not over-state.
    lead = PublicSignal(
        month=8,
        signal_type="business_model_change",
        headline="Acme announces strategic pivot",
        severity=0.60,
        source="Event Registry / NewsAPI.ai",
    )
    assert PublicSignalOut(**lead.to_dict()).corroborated is False


# --------------------------------------------------------------------------- #
# UC8 — DriftSubjectDetail exposes the is_name_changed flag (contract test)    #
# --------------------------------------------------------------------------- #

async def test_subject_detail_exposes_is_name_changed(client: AsyncClient) -> None:
    """DriftSubjectDetail must always carry the boolean ``is_name_changed`` flag
    (UC8 follow-up), mirroring the summary so the detail panel can render the
    identity-reset re-KYC treatment. Present and correctly typed for every
    subject, regardless of whether a name change was detected.
    """
    listing = await client.get("/api/v1/drift/subjects")
    assert listing.status_code == 200
    subjects = listing.json()
    assert subjects, "synthetic book should not be empty"

    drift_id = subjects[0]["drift_id"]
    detail = await client.get(f"/api/v1/drift/subjects/{drift_id}")
    assert detail.status_code == 200

    body = detail.json()
    assert "is_name_changed" in body, (
        f"is_name_changed missing from detail. Keys: {list(body.keys())}"
    )
    assert isinstance(body["is_name_changed"], bool)
