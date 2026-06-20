"""BDD step definitions for time_travel.feature.

These scenarios pin down the Time-Travel Audit's honesty guarantee: the as-of
replay recomputes a customer's score using ONLY information available up to the
as-of month, so any lead time it reports is causal, not hindsight.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.drift.public_intel import assess_public_risk, generate_signals_for_customer
from app.drift.simulator import generate_customer
from app.drift.timetravel import replay_as_of, replay_trajectory

scenarios("features/time_travel.feature")

# A representative present-day contagion risk for the wired customer. Its only
# role is to be switched ON at the listing month and OFF before it.
PROPAGATED_RISK_FINAL = 0.5


@pytest.fixture
def context() -> dict:
    return {}


@given(parsers.parse('the "{scenario}" drift customer wired to a sanctions listing'))
def make_wired_customer(scenario: str, context: dict) -> None:
    cust = generate_customer(
        drift_id="bdd-tt",
        name="Time-Travel Test Customer",
        scenario=scenario,
        seed=42,
    )
    assert cust.sanctions_month is not None, "scenario must end in a listing"
    context["customer"] = cust
    context["listing_month"] = cust.sanctions_month


@when("the score is replayed as of a month before the listing")
def replay_before_listing(context: dict) -> None:
    cust = context["customer"]
    # Several months before the listing — early enough that later public
    # signals still exist and must be truncated away.
    month_t = context["listing_month"] - 5
    context["month_t"] = month_t
    context["point"] = replay_as_of(
        cust,
        month_t,
        propagated_risk_final=PROPAGATED_RISK_FINAL,
        contagion_listing_month=context["listing_month"],
    )


@then("the replay uses no public signal dated after that month")
def assert_no_future_signals(context: dict) -> None:
    cust = context["customer"]
    month_t = context["month_t"]
    all_signals = generate_signals_for_customer(
        cust.drift_id,
        cust.name,
        cust.scenario,
        months=cust.months,
        drift_start_month=cust.drift_start_month,
        seed=hash(cust.drift_id) % 9999,
    )
    # There must genuinely be future signals to exclude, otherwise the test
    # proves nothing.
    assert any(s.month > month_t for s in all_signals), (
        "scenario has no post-as-of signals — cannot demonstrate truncation"
    )
    past_only = [s for s in all_signals if s.month <= month_t]
    expected = assess_public_risk(past_only, months=cust.months).public_risk
    assert context["point"].public_risk == pytest.approx(round(expected, 3), abs=1e-9), (
        "as-of public risk reflects signals dated after the as-of month"
    )


@then("contagion risk is inactive before the listing month")
def assert_contagion_inactive(context: dict) -> None:
    point = context["point"]
    assert context["month_t"] < context["listing_month"]
    assert point.contagion_active is False, (
        "contagion was active before the sanctions listing existed"
    )


@when("the full as-of trajectory is replayed")
def replay_full_trajectory(context: dict) -> None:
    cust = context["customer"]
    context["trajectory"] = replay_trajectory(
        cust,
        propagated_risk_final=PROPAGATED_RISK_FINAL,
        contagion_listing_month=context["listing_month"],
    )


@then("the alert month precedes the sanctions month")
def assert_alert_precedes_listing(context: dict) -> None:
    traj = context["trajectory"]
    assert traj["alert_month"] is not None, "replay never crossed the alert threshold"
    assert traj["alert_month"] < traj["sanctions_month"], (
        f"alert month {traj['alert_month']} did not precede "
        f"sanctions month {traj['sanctions_month']}"
    )


@then("the lead time is positive")
def assert_positive_lead(context: dict) -> None:
    lead = context["trajectory"]["lead_time_months"]
    assert lead is not None and lead > 0, f"expected positive lead time, got {lead!r}"


@when("the as-of score at a month is recomputed from a future-truncated history")
def recompute_with_corrupted_future(context: dict) -> None:
    cust = context["customer"]
    month_t = context["listing_month"] - 2
    context["month_t"] = month_t

    baseline = replay_as_of(
        cust,
        month_t,
        propagated_risk_final=PROPAGATED_RISK_FINAL,
        contagion_listing_month=context["listing_month"],
    )

    # Corrupt every observation AFTER the as-of month. A causal as-of replay
    # must ignore these, so the as-of-T score cannot change.
    corrupted = copy.deepcopy(cust)
    for arrays in (
        corrupted.monthly_volume,
        corrupted.counterparty_risk,
        corrupted.corridor_risk,
        corrupted.margin_ratio,
    ):
        for m in range(month_t + 1, corrupted.months):
            arrays[m] = np.full_like(arrays[m], 1e6)

    corrupted_point = replay_as_of(
        corrupted,
        month_t,
        propagated_risk_final=PROPAGATED_RISK_FINAL,
        contagion_listing_month=context["listing_month"],
    )
    context["baseline_score"] = baseline.as_of_score
    context["corrupted_score"] = corrupted_point.as_of_score


@then("the two as-of scores are identical")
def assert_scores_identical(context: dict) -> None:
    assert context["baseline_score"] == context["corrupted_score"], (
        f"future data leaked into the as-of score: "
        f"{context['baseline_score']} != {context['corrupted_score']}"
    )
