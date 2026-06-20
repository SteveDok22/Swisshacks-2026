"""BDD step definitions for drift_detection.feature."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.drift.causal import causal_assessment
from app.drift.public_intel import assess_public_risk, generate_signals_for_customer
from app.drift.simulator import generate_book, generate_customer
from app.drift.stability import assess_stability, cohort_volatility

scenarios("features/drift_detection.feature")


@pytest.fixture
def context() -> dict:
    return {}


@given(parsers.parse('the "{scenario}" synthetic customer with seed {seed:d}'))
def make_synthetic_customer(scenario: str, seed: int, context: dict) -> None:
    context["customer"] = generate_customer(
        drift_id="bdd-test",
        name="BDD Test Customer",
        scenario=scenario,
        seed=seed,
    )


@when("causal assessment is run on the customer")
def run_causal_assessment(context: dict) -> None:
    context["verdict"] = causal_assessment(context["customer"].causal_windows())


@then(parsers.parse('the causal label is "{label}"'))
def assert_causal_label(label: str, context: dict) -> None:
    actual = context["verdict"].label
    assert actual == label, (
        f"Expected label={label!r} but got {actual!r} "
        f"(causal_llr={context['verdict'].causal_llr:.3f})"
    )


@given("the book cohort volatility is computed")
def compute_book_cohort_cv(context: dict) -> None:
    book = generate_book()
    context["cohort_cv"] = cohort_volatility([c.monthly_volume for c in book])


@when("stability is assessed with the customer's environment")
def run_stability_assessment(context: dict) -> None:
    cust = context["customer"]
    signals = generate_signals_for_customer(
        cust.drift_id,
        cust.name,
        cust.scenario,
        months=cust.months,
        drift_start_month=cust.drift_start_month,
        seed=hash(cust.drift_id) % 9999,
    )
    public_risk = assess_public_risk(signals, months=cust.months).public_risk
    context["stability"] = assess_stability(
        cust.monthly_volume,
        context["cohort_cv"],
        counterparty_monthly=cust.counterparty_risk,
        corridor_monthly=cust.corridor_risk,
        public_risk=public_risk,
    )


@then("is_suspicious is true")
def assert_is_suspicious(context: dict) -> None:
    result = context["stability"]
    assert result.is_suspicious, (
        f"Expected is_suspicious=True but got False "
        f"(suspicion={result.suspicion:.3f}, "
        f"stability_anomaly={result.stability_anomaly:.3f}, "
        f"env_movement={result.environmental_movement:.3f})"
    )
