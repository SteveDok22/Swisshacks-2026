"""BDD step definitions for contagion.feature."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.drift.contagion import OwnershipGraph

scenarios("features/contagion.feature")


@pytest.fixture
def context() -> dict:
    return {}


@given(parsers.parse('a sanctioned seed entity "{seed_id}"'))
def sanctioned_entity(seed_id: str, context: dict) -> None:
    g = OwnershipGraph()
    g.add_entity(seed_id, name=f"Sanctioned: {seed_id}")
    context["graph"] = g
    context["seed_id"] = seed_id


@given(parsers.parse('a customer "{cust_id}" who is directly connected to the seed'))
def direct_customer(cust_id: str, context: dict) -> None:
    g: OwnershipGraph = context["graph"]
    g.add_entity(cust_id, name=cust_id, is_customer=True)
    g.add_ownership(context["seed_id"], cust_id, 0.85)
    context["direct_id"] = cust_id


@given(parsers.parse('a customer "{cust_id}" one hop from the seed'))
def one_hop_customer(cust_id: str, context: dict) -> None:
    g: OwnershipGraph = context["graph"]
    g.add_entity(cust_id, name=cust_id, is_customer=True)
    g.add_ownership(context["seed_id"], cust_id, 0.80)
    context["near_id"] = cust_id


@given(parsers.parse('a customer "{cust_id}" two hops from the seed'))
def two_hop_customer(cust_id: str, context: dict) -> None:
    g: OwnershipGraph = context["graph"]
    g.add_entity("intermediate", name="Shell Co (intermediate)")
    g.add_ownership(context["seed_id"], "intermediate", 0.60)
    g.add_entity(cust_id, name=cust_id, is_customer=True)
    g.add_ownership("intermediate", cust_id, 0.50)
    context["far_id"] = cust_id


@when("contagion is propagated from the seed")
def propagate_contagion(context: dict) -> None:
    g: OwnershipGraph = context["graph"]
    context["result"] = g.propagate([context["seed_id"]])


@then(parsers.parse('the customer "{cust_id}" has propagated_risk above 0.1'))
def assert_risk_above_threshold(cust_id: str, context: dict) -> None:
    risk = context["result"].propagated_risk[cust_id]
    assert risk > 0.1, f"Expected propagated_risk > 0.1 for {cust_id!r}, got {risk:.4f}"


@then(parsers.parse('the customer "{near_id}" has higher propagated_risk than "{far_id}"'))
def assert_near_higher_than_far(near_id: str, far_id: str, context: dict) -> None:
    near_risk = context["result"].propagated_risk[near_id]
    far_risk = context["result"].propagated_risk[far_id]
    assert near_risk > far_risk, (
        f"Expected {near_id!r} ({near_risk:.4f}) > {far_id!r} ({far_risk:.4f})"
    )
