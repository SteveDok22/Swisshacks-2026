"""Regression tests for the P2 drift-engine cleanups."""

from __future__ import annotations

from unittest.mock import Mock

import app.drift.service as drift_service
from app.core.config import (
    DRIFT_CONFIRMATION_LIFT_RANGE,
    DRIFT_CONFIRMATION_MAX_AMPLIFICATION,
    DRIFT_INTERNAL_ACCUMULATED_WEIGHT,
    DRIFT_INTERNAL_CONTAGION_WEIGHT,
    DRIFT_INTERNAL_VELOCITY_WEIGHT,
    DRIFT_PUBLIC_RISK_WEIGHT,
)


def test_drift_scoring_weights_are_named_configuration_constants():
    assert DRIFT_INTERNAL_VELOCITY_WEIGHT == 0.60
    assert DRIFT_INTERNAL_ACCUMULATED_WEIGHT == 0.25
    assert DRIFT_INTERNAL_CONTAGION_WEIGHT == 0.40
    assert DRIFT_PUBLIC_RISK_WEIGHT == 0.85
    assert DRIFT_CONFIRMATION_LIFT_RANGE == 3.0
    assert DRIFT_CONFIRMATION_MAX_AMPLIFICATION == 0.35


def test_get_drift_engine_warns_when_process_local_singleton_is_created(monkeypatch):
    engine = object()
    engine_factory = Mock(return_value=engine)
    warning = Mock()
    monkeypatch.setattr(drift_service, "_engine", None)
    monkeypatch.setattr(drift_service, "DriftEngine", engine_factory)
    monkeypatch.setattr(drift_service.logger, "warning", warning)

    first = drift_service.get_drift_engine()
    second = drift_service.get_drift_engine()

    assert first is engine
    assert second is engine
    engine_factory.assert_called_once_with()
    warning.assert_called_once_with(
        "drift_engine_single_worker_required",
        reason=(
            "DriftEngine uses process-local mutable state; configure exactly "
            "one API worker until state is moved to a shared store."
        ),
    )


async def test_timeline_is_available_only_on_canonical_customer_route(client):
    canonical_response = await client.get("/api/v1/drift/customers/drift-001")
    removed_response = await client.get("/api/v1/drift/customers/drift-001/timeline")

    assert canonical_response.status_code == 200
    assert canonical_response.json()["timeline"]
    assert removed_response.status_code == 404
