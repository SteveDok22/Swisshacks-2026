"""
Tests for app/sources/whois.py - WhoisAdapter RDAP implementation.

All HTTP calls are mocked. The tests cover RDAP normalization, no-key/free
metadata, graceful network failure, and the roadmap's domain-change signal paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.sources.base import EntitySnapshot
from app.sources.cost import AdapterStatus, SourceCost
from app.sources.whois import (
    WhoisAdapter,
    _domain_age_severity,
    _name_to_domain_slug,
    _normalize_domain,
    _resolve_domain,
)

_DOMAIN = "acme.example"

_RDAP_RECORD: dict[str, Any] = {
    "handle": "D-EXAMPLE",
    "events": [
        {"eventAction": "registration", "eventDate": "2026-06-10T12:00:00Z"},
        {"eventAction": "last changed", "eventDate": "2026-06-15T08:00:00Z"},
    ],
    "status": ["active"],
    "entities": [
        {
            "roles": ["registrar"],
            "vcardArray": [
                "vcard",
                [["fn", {}, "text", "Example Registrar AG"]],
            ],
        },
        {
            "roles": ["registrant"],
            "vcardArray": [
                "vcard",
                [
                    ["fn", {}, "text", "Acme Domain Contact"],
                    ["org", {}, "text", "Acme Holdings AG"],
                ],
            ],
        },
    ],
}


def _mock_response(status_code: int, payload: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json = MagicMock(return_value=payload or {})
    return resp


def _baseline(registrant_org: str = "Old Holdings AG") -> EntitySnapshot:
    return EntitySnapshot(
        drift_id="drift-whois-001",
        name=registrant_org,
        source="whois",
        raw_data={
            "domain": _DOMAIN,
            "registered_at": "2020-01-01T00:00:00Z",
            "registrant_org": registrant_org,
        },
    )


class TestWhoisMetadata:
    def test_source_name(self):
        assert WhoisAdapter.source_name == "whois"

    def test_cost_is_free(self):
        assert WhoisAdapter.cost is SourceCost.FREE

    def test_status_is_planned(self):
        assert WhoisAdapter.status is AdapterStatus.PLANNED

    def test_requires_no_api_key(self):
        assert WhoisAdapter.requires_api_key is False

    def test_use_cases_match_roadmap(self):
        assert set(WhoisAdapter.use_cases) == {8, 9}

    def test_signal_types_declared(self):
        assert WhoisAdapter.signal_types == ("domain_change", "domain_age")

    def test_record_url_normalizes_domain(self):
        adapter = WhoisAdapter()
        assert adapter.record_url("https://www.Acme.Example/path") == (
            "https://rdap.org/domain/acme.example"
        )

    async def test_async_context_manager_does_not_close_injected_client(self):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock()
        async with WhoisAdapter(http_client=mock_client):
            pass
        mock_client.aclose.assert_not_called()


class TestDomainHelpers:
    def test_normalize_domain_from_url(self):
        assert _normalize_domain("https://www.Acme.Example/path") == "acme.example"

    def test_normalize_domain_rejects_blank(self):
        assert _normalize_domain("   ") is None

    def test_name_to_domain_slug_removes_legal_suffix(self):
        assert _name_to_domain_slug("Acme Holdings AG") == "acmeholdings"

    def test_resolve_prefers_explicit_domain(self):
        assert _resolve_domain(
            "Ignored AG", domain="example.com", website="other.example"
        ) == "example.com"

    def test_resolve_falls_back_to_name_slug_com(self):
        assert _resolve_domain("Acme Holdings AG") == "acmeholdings.com"

    @pytest.mark.parametrize(
        ("age_days", "severity"),
        [(10, 0.80), (120, 0.45), (365, None)],
    )
    def test_domain_age_severity(self, age_days: int, severity: float | None):
        assert _domain_age_severity(age_days) == severity


class TestWhoisNormalize:
    def setup_method(self):
        self.adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))

    def test_snapshot_fields(self):
        snap = self.adapter._normalize("drift-1", "Acme AG", _DOMAIN, _RDAP_RECORD)
        assert snap.drift_id == "drift-1"
        assert snap.name == "Acme Holdings AG"
        assert snap.source == "whois"
        assert snap.raw_data["domain"] == _DOMAIN
        assert snap.raw_data["registered_at"] == "2026-06-10T12:00:00Z"
        assert snap.raw_data["last_changed"] == "2026-06-15T08:00:00Z"
        assert snap.raw_data["registrar"] == "Example Registrar AG"
        assert snap.raw_data["registrant_org"] == "Acme Holdings AG"
        assert snap.raw_data["status"] == ["active"]

    def test_registrant_falls_back_to_fn(self):
        record = {
            "entities": [
                {
                    "roles": ["registrant"],
                    "vcardArray": ["vcard", [["fn", {}, "text", "Fallback Contact"]]],
                }
            ]
        }
        snap = self.adapter._normalize("drift-1", "Acme AG", _DOMAIN, record)
        assert snap.name == "Fallback Contact"
        assert snap.raw_data["registrant_org"] == "Fallback Contact"


class TestWhoisFetch:
    def _adapter_with_get(self, side_effect) -> WhoisAdapter:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=side_effect)
        return WhoisAdapter(http_client=mock_client)

    async def test_fetch_returns_snapshot_on_200(self):
        adapter = self._adapter_with_get(lambda url, **kw: _mock_response(200, _RDAP_RECORD))
        snap = await adapter.fetch("drift-1", "Acme AG", domain=_DOMAIN)
        assert snap is not None
        assert snap.source == "whois"
        assert snap.raw_data["registrant_org"] == "Acme Holdings AG"

    async def test_fetch_uses_name_heuristic_when_domain_absent(self):
        adapter = self._adapter_with_get(lambda url, **kw: _mock_response(200, _RDAP_RECORD))
        snap = await adapter.fetch("drift-1", "Acme Holdings AG")
        assert snap is not None
        assert snap.raw_data["domain"] == "acmeholdings.com"

    async def test_fetch_returns_none_on_404(self):
        adapter = self._adapter_with_get(lambda url, **kw: _mock_response(404))
        assert await adapter.fetch("drift-1", "Missing AG", domain="missing.example") is None

    async def test_fetch_returns_none_on_transport_error(self):
        async def raise_transport(url, **kw):
            raise httpx.TransportError("timeout")

        adapter = self._adapter_with_get(raise_transport)
        assert await adapter.fetch("drift-1", "Acme AG", domain=_DOMAIN) is None

    async def test_fetch_returns_none_on_non_json_response(self):
        resp = _mock_response(200)
        resp.json = MagicMock(side_effect=ValueError("not json"))
        adapter = self._adapter_with_get(lambda url, **kw: resp)
        assert await adapter.fetch("drift-1", "Acme AG", domain=_DOMAIN) is None


class TestWhoisFetchSignals:
    async def test_registrant_change_emits_domain_change_signal(self):
        adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))
        current = adapter._normalize("drift-1", "Acme AG", _DOMAIN, _RDAP_RECORD)
        signals = await adapter.fetch_signals(
            "drift-1",
            "Acme AG",
            since_month=8,
            baseline=_baseline("Old Holdings AG"),
            current=current,
        )

        assert len(signals) == 1
        assert signals[0].signal_type == "domain_change"
        assert signals[0].severity == pytest.approx(0.70)
        assert "Old Holdings AG" in signals[0].headline
        assert "Acme Holdings AG" in signals[0].headline
        assert signals[0].source_url == "https://rdap.org/domain/acme.example"

    async def test_same_registrant_emits_no_diff_signal(self):
        adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))
        current = adapter._normalize("drift-1", "Acme AG", _DOMAIN, _RDAP_RECORD)
        signals = await adapter.fetch_signals(
            "drift-1",
            "Acme AG",
            baseline=_baseline("Acme Holdings AG"),
            current=current,
        )
        assert signals == []

    async def test_cross_source_baseline_is_ignored(self):
        adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))
        current = adapter._normalize("drift-1", "Acme AG", _DOMAIN, _RDAP_RECORD)
        baseline = EntitySnapshot(
            drift_id="drift-1",
            name="Old",
            source="gleif",
            raw_data={"registrant_org": "Old"},
        )
        signals = await adapter.fetch_signals(
            "drift-1", "Acme AG", baseline=baseline, current=current
        )
        assert signals == []

    async def test_young_domain_with_old_company_claim_emits_signal(self):
        adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))
        young_date = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {**_RDAP_RECORD, "events": [{"eventAction": "registration", "eventDate": young_date}]}
        current = adapter._normalize("drift-1", "Acme AG", _DOMAIN, record)
        signals = await adapter.fetch_signals(
            "drift-1",
            "Acme AG",
            current=current,
            claimed_company_age_days=365 * 5,
        )
        assert len(signals) == 1
        assert signals[0].signal_type == "domain_age"
        assert signals[0].severity == pytest.approx(0.80)
        assert "registered recently" in signals[0].headline

    async def test_young_domain_without_company_age_hint_is_not_a_signal(self):
        adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))
        current = adapter._normalize("drift-1", "Acme AG", _DOMAIN, _RDAP_RECORD)
        signals = await adapter.fetch_signals("drift-1", "Acme AG", current=current)
        assert signals == []

    async def test_recent_but_not_very_young_domain_has_medium_severity(self):
        adapter = WhoisAdapter(http_client=MagicMock(spec=httpx.AsyncClient))
        medium_date = (datetime.now(UTC) - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {
            **_RDAP_RECORD,
            "events": [{"eventAction": "registration", "eventDate": medium_date}],
        }
        current = adapter._normalize("drift-1", "Acme AG", _DOMAIN, record)
        signals = await adapter.fetch_signals(
            "drift-1",
            "Acme AG",
            current=current,
            claimed_company_age_days=365 * 5,
        )
        assert len(signals) == 1
        assert signals[0].signal_type == "domain_age"
        assert signals[0].severity == pytest.approx(0.45)
