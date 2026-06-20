"""Tests for T2 LLM adjudication in the drift scan flow."""

from __future__ import annotations

import json

from app.drift.cascade import CascadeRouter
from app.drift.service import DriftEngine


class FakeAnthropicClient:
    def __init__(self, *, is_mock: bool = True, response: str | None = None) -> None:
        self.is_mock = is_mock
        self.response = response or json.dumps(
            {
                "verdict": "risk",
                "confidence": 0.81,
                "rationale": "Structured evidence supports a risk-shaped drift hypothesis.",
                "key_evidence": ["risk-shaped causal label"],
                "recommended_action": "Escalate to enhanced due diligence",
            }
        )
        self.calls: list[dict[str, object]] = []

    def complete(self, prompt: str, **kwargs):
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        return self.response, False


def test_scan_calls_llm_for_t2_customers_only(monkeypatch):
    engine = DriftEngine()
    fake = FakeAnthropicClient(is_mock=True)
    monkeypatch.setattr("app.drift.service.get_anthropic_client", lambda: fake)

    report = engine.scan()

    expected_t2 = report.tier_counts["T2_LLM"]
    assert expected_t2 > 0
    assert len(fake.calls) == expected_t2
    assert report.actual_t2_llm_calls == expected_t2
    assert report.mock_t2_llm_calls == expected_t2
    assert report.real_t2_llm_calls == 0
    assert len(report.llm_adjudications) == expected_t2
    assert report.llm_adjudications[0].response["verdict"] == "risk"


def test_scan_does_not_call_llm_when_no_customer_reaches_t2(monkeypatch):
    engine = DriftEngine()
    engine._router = CascadeRouter(t1_drift_threshold=999.0, t2_drift_threshold=999.0)
    fake = FakeAnthropicClient(is_mock=True)
    monkeypatch.setattr("app.drift.service.get_anthropic_client", lambda: fake)

    report = engine.scan()

    assert report.tier_counts["T2_LLM"] == 0
    assert len(fake.calls) == 0
    assert report.actual_t2_llm_calls == 0
    assert report.real_t2_llm_calls == 0
    assert report.mock_t2_llm_calls == 0
    assert report.llm_adjudications == []


def test_invalid_llm_json_returns_safe_fallback(monkeypatch):
    engine = DriftEngine()
    fake = FakeAnthropicClient(is_mock=True, response="not json")
    monkeypatch.setattr("app.drift.service.get_anthropic_client", lambda: fake)

    report = engine.scan()

    assert report.actual_t2_llm_calls > 0
    adjudication = report.llm_adjudications[0]
    assert adjudication.response == {
        "verdict": "ambiguous",
        "confidence": 0.0,
        "rationale": "LLM response could not be parsed as valid JSON.",
        "key_evidence": [],
        "recommended_action": "Request information",
    }
