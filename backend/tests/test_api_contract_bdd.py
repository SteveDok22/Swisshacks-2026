"""BDD step definitions for api_contract.feature.

Uses the async `client` fixture from conftest.py (in-memory SQLite, ASGI transport).
Requires pytest-bdd >= 7.0 and asyncio_mode = "auto" (already set in pyproject.toml).
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from pytest_bdd import given, parsers, scenarios, then, when

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
