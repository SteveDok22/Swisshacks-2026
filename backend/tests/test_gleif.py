"""
Tests for app/sources/gleif.py — GleifAdapter implementation.

Covers:
- Adapter metadata (cost, status, signal_types, use_cases)
- _normalize() and the pure helper functions (_extract_name, _extract_legal_form,
  _extract_address, _extract_status) with representative GLEIF JSON payloads
- fetch() with mocked internal helpers: happy path, name-lookup fallback,
  LEI not found, transport errors, parent/children ownership mapping
- fetch_signals() returns empty list (registry diff adapter)
- record_url() formats the GLEIF search URL correctly
- Integration: snapshot produced by fetch() feeds diff_snapshots() and
  generates expected SnapshotDiff objects when compared to a baseline
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.sources.base import EntitySnapshot, SnapshotDiff, diff_snapshots
from app.sources.cost import AdapterStatus, SourceCost
from app.sources.gleif import (
    GleifAdapter,
    _extract_address,
    _extract_legal_form,
    _extract_name,
    _extract_status,
)


# ---------------------------------------------------------------------------
# Shared sample data — representative GLEIF API payloads
# ---------------------------------------------------------------------------

_LEI = "529900T8BM49AURSDO55"
_PARENT_LEI = "PARENTLEI00000000001X"
_CHILD_LEI_A = "CHILDLEIA0000000001X"
_CHILD_LEI_B = "CHILDLEIB0000000002X"

_LEI_RECORD_ACTIVE: dict = {
    "data": {
        "type": "lei-records",
        "id": _LEI,
        "attributes": {
            "lei": _LEI,
            "entity": {
                "legalName": {"name": "Alpine Holdings AG", "language": "en"},
                "status": "ACTIVE",
                "jurisdiction": "CH",
                "legalAddress": {
                    "addressLines": ["Bahnhofstrasse 12"],
                    "city": "Zurich",
                    "country": "CH",
                    "postalCode": "8001",
                },
                "legalForm": {"id": "AG", "other": None},
            },
            "registration": {
                "status": "ISSUED",
                "initialRegistrationDate": "2015-03-01T00:00:00Z",
                "lastUpdateDate": "2024-11-01T00:00:00Z",
            },
        },
    }
}

_LEI_RECORD_ANNULLED: dict = {
    "data": {
        "type": "lei-records",
        "id": _LEI,
        "attributes": {
            "lei": _LEI,
            "entity": {
                "legalName": {"name": "Alpine Holdings AG", "language": "en"},
                "status": "ACTIVE",
                "jurisdiction": "CH",
                "legalAddress": {
                    "addressLines": ["Bahnhofstrasse 12"],
                    "city": "Zurich",
                    "country": "CH",
                    "postalCode": "8001",
                },
                "legalForm": {"id": "AG", "other": None},
            },
            "registration": {
                "status": "ANNULLED",
                "initialRegistrationDate": "2015-03-01T00:00:00Z",
                "lastUpdateDate": "2026-01-10T00:00:00Z",
            },
        },
    }
}

_LEI_RECORD_INACTIVE_ENTITY: dict = {
    "data": {
        "type": "lei-records",
        "id": _LEI,
        "attributes": {
            "lei": _LEI,
            "entity": {
                "legalName": {"name": "Ghost Corp", "language": "en"},
                "status": "INACTIVE",
                "jurisdiction": "DE",
                "legalAddress": {},
                "legalForm": {},
            },
            "registration": {"status": "RETIRED"},
        },
    }
}

_PARENT_RECORD: dict = {
    "data": {
        "type": "lei-records",
        "id": _PARENT_LEI,
        "attributes": {"lei": _PARENT_LEI},
    }
}

_CHILDREN_RECORD: dict = {
    "data": [
        {"type": "lei-records", "id": _CHILD_LEI_A, "attributes": {"lei": _CHILD_LEI_A}},
        {"type": "lei-records", "id": _CHILD_LEI_B, "attributes": {"lei": _CHILD_LEI_B}},
    ]
}

_NAME_LOOKUP_RESULT: dict = {
    "data": [
        {
            "type": "lei-records",
            "id": _LEI,          # top-level JSON:API id — preferred by _lookup_lei_by_name
            "attributes": {"lei": _LEI},
        }
    ]
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, payload: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json = MagicMock(return_value=payload or {})
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


def _make_adapter(
    lei_record: dict | None = None,
    parent: dict | None = None,
    children: dict | None = None,
    lei_status: int = 200,
    parent_status: int = 200,
    children_status: int = 200,
) -> GleifAdapter:
    """Build an adapter with mocked internal helpers."""
    adapter = GleifAdapter()
    adapter._get_lei_record = AsyncMock(
        return_value=lei_record if lei_status == 200 else None
    )
    adapter._get_parent_lei = AsyncMock(
        return_value=(
            parent.get("data", {}).get("attributes", {}).get("lei") if parent else None
        )
    )
    adapter._get_children_leis = AsyncMock(
        return_value=(
            [item["attributes"]["lei"] for item in children.get("data", [])]
            if children
            else []
        )
    )
    return adapter


def _baseline(
    drift_id: str = "drift-gleif-001",
    name: str = "Alpine Holdings AG",
    jurisdiction: str = "CH",
    dissolution_status: str = "active",
    beneficial_owners: list[str] | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        drift_id=drift_id,
        name=name,
        source="gleif",
        jurisdiction=jurisdiction,
        dissolution_status=dissolution_status,
        beneficial_owners=beneficial_owners or [],
    )


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------

class TestGleifMetadata:
    def test_source_name(self):
        assert GleifAdapter.source_name == "gleif"

    def test_cost_is_free(self):
        assert GleifAdapter.cost is SourceCost.FREE

    def test_status_is_planned(self):
        assert GleifAdapter.status is AdapterStatus.PLANNED

    def test_requires_no_api_key(self):
        assert GleifAdapter.requires_api_key is False

    def test_use_cases_match_roadmap(self):
        assert set(GleifAdapter.use_cases) == {3, 4, 5, 8, 10}

    def test_signal_types_declared(self):
        # adverse_media is excluded — GLEIF is a pure registry source with no
        # news/media data; it cannot emit adverse_media signals.
        expected = {"name_change", "jurisdiction_change", "status_change", "ownership_change"}
        assert set(GleifAdapter.signal_types) == expected

    def test_record_url_formats_correctly(self):
        adapter = GleifAdapter()
        url = adapter.record_url(_LEI)
        assert _LEI in url
        assert url.startswith("https://search.gleif.org")

    def test_is_usable(self):
        assert GleifAdapter.is_usable() is True

    def test_is_not_skipped(self):
        assert GleifAdapter.is_skipped() is False

    def test_is_free(self):
        assert GleifAdapter.is_free() is True

    async def test_aclose_does_not_raise(self):
        adapter = GleifAdapter()
        await adapter.aclose()  # must not raise

    async def test_async_context_manager_closes_client(self):
        closed: list[bool] = []
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock(side_effect=lambda: closed.append(True))
        # Injected client — adapter does NOT own it, so aclose is not called.
        async with GleifAdapter(http_client=mock_client):
            pass
        assert closed == []  # external clients are never closed by the adapter


# ---------------------------------------------------------------------------
# Pure normalisation helpers
# ---------------------------------------------------------------------------

class TestExtractName:
    def test_dict_form(self):
        assert _extract_name({"legalName": {"name": "Acme AG", "language": "en"}}) == "Acme AG"

    def test_string_form(self):
        assert _extract_name({"legalName": "Flat String Corp"}) == "Flat String Corp"

    def test_missing_returns_empty_string(self):
        assert _extract_name({}) == ""

    def test_none_name_in_dict(self):
        assert _extract_name({"legalName": {"language": "en"}}) == ""


class TestExtractLegalForm:
    def test_id_field_preferred(self):
        assert _extract_legal_form({"legalForm": {"id": "AG", "other": None}}) == "AG"

    def test_other_field_fallback(self):
        assert _extract_legal_form({"legalForm": {"id": None, "other": "GmbH"}}) == "GmbH"

    def test_missing_returns_none(self):
        assert _extract_legal_form({}) is None

    def test_empty_dict_returns_none(self):
        assert _extract_legal_form({"legalForm": {}}) is None

    def test_non_dict_returns_none(self):
        assert _extract_legal_form({"legalForm": "AG"}) is None


class TestExtractAddress:
    def test_full_address(self):
        entity = {
            "legalAddress": {
                "addressLines": ["Paradeplatz 8"],
                "city": "Zurich",
                "country": "CH",
            }
        }
        result = _extract_address(entity)
        assert result == "Paradeplatz 8, Zurich, CH"

    def test_city_and_country_only(self):
        entity = {"legalAddress": {"city": "Geneva", "country": "CH"}}
        assert _extract_address(entity) == "Geneva, CH"

    def test_missing_returns_none(self):
        assert _extract_address({}) is None

    def test_empty_address_returns_none(self):
        assert _extract_address({"legalAddress": {}}) is None

    def test_non_dict_address_returns_none(self):
        assert _extract_address({"legalAddress": "123 Main St"}) is None


class TestExtractStatus:
    def test_issued_is_active(self):
        assert _extract_status({"status": "ACTIVE"}, {"status": "ISSUED"}) == "active"

    def test_annulled_is_dissolved(self):
        assert _extract_status({"status": "ACTIVE"}, {"status": "ANNULLED"}) == "dissolved"

    def test_retired_is_dissolved(self):
        assert _extract_status({}, {"status": "RETIRED"}) == "dissolved"

    def test_lapsed_is_lapsed_not_active(self):
        # LAPSED means the LEI registration expired — the entity's legal state
        # is UNCONFIRMED, not "active". Mapping to "lapsed" lets the diff layer
        # detect ISSUED→LAPSED transitions instead of hiding them.
        assert _extract_status({"status": "ACTIVE"}, {"status": "LAPSED"}) == "lapsed"

    def test_pending_validation_is_none(self):
        # In-flight registration — true entity status unknown.
        assert _extract_status({}, {"status": "PENDING_VALIDATION"}) is None

    def test_inactive_entity_overrides_registration(self):
        # Entity INACTIVE takes precedence even if registration says ISSUED.
        assert _extract_status({"status": "INACTIVE"}, {"status": "ISSUED"}) == "dissolved"

    def test_unknown_status_returns_none(self):
        assert _extract_status({}, {"status": "UNKNOWN_STATUS"}) is None

    def test_missing_status_returns_none(self):
        assert _extract_status({}, {}) is None


# ---------------------------------------------------------------------------
# GleifAdapter._normalize() — integration of the pure helpers
# ---------------------------------------------------------------------------

class TestGleifNormalize:
    def setup_method(self):
        self.adapter = GleifAdapter()

    def test_active_entity_snapshot_fields(self):
        snap = self.adapter._normalize("drift-001", _LEI, _LEI_RECORD_ACTIVE, None, [])
        assert snap.drift_id == "drift-001"
        assert snap.name == "Alpine Holdings AG"
        assert snap.source == "gleif"
        assert snap.jurisdiction == "CH"
        assert snap.legal_form == "AG"
        assert snap.registered_address == "Bahnhofstrasse 12, Zurich, CH"
        assert snap.dissolution_status == "active"
        assert snap.beneficial_owners == []
        assert snap.officers == []

    def test_raw_data_contains_lei_and_statuses(self):
        snap = self.adapter._normalize("drift-001", _LEI, _LEI_RECORD_ACTIVE, None, [])
        assert snap.raw_data["lei"] == _LEI
        assert snap.raw_data["registration_status"] == "ISSUED"
        assert snap.raw_data["entity_status"] == "ACTIVE"

    def test_annulled_maps_to_dissolved(self):
        snap = self.adapter._normalize("drift-001", _LEI, _LEI_RECORD_ANNULLED, None, [])
        assert snap.dissolution_status == "dissolved"

    def test_inactive_entity_maps_to_dissolved(self):
        snap = self.adapter._normalize("drift-001", _LEI, _LEI_RECORD_INACTIVE_ENTITY, None, [])
        assert snap.dissolution_status == "dissolved"

    def test_parent_lei_goes_into_beneficial_owners(self):
        snap = self.adapter._normalize("drift-001", _LEI, _LEI_RECORD_ACTIVE, _PARENT_LEI, [])
        assert snap.beneficial_owners == [_PARENT_LEI]

    def test_children_leis_go_into_officers(self):
        snap = self.adapter._normalize(
            "drift-001", _LEI, _LEI_RECORD_ACTIVE, None, [_CHILD_LEI_A, _CHILD_LEI_B]
        )
        assert snap.officers == [_CHILD_LEI_A, _CHILD_LEI_B]

    def test_no_parent_means_empty_beneficial_owners(self):
        snap = self.adapter._normalize("drift-001", _LEI, _LEI_RECORD_ACTIVE, None, [])
        assert snap.beneficial_owners == []

    def test_no_jurisdiction_in_entity(self):
        record = {
            "data": {
                "attributes": {
                    "entity": {"legalName": {"name": "Corp"}, "status": "ACTIVE"},
                    "registration": {"status": "ISSUED"},
                }
            }
        }
        snap = self.adapter._normalize("d", "L", record, None, [])
        assert snap.jurisdiction is None


# ---------------------------------------------------------------------------
# GleifAdapter.fetch() — mocked internal helpers
# ---------------------------------------------------------------------------

class TestGleifFetch:
    async def test_happy_path_returns_entity_snapshot(self):
        adapter = _make_adapter(lei_record=_LEI_RECORD_ACTIVE)
        snap = await adapter.fetch("drift-001", "Alpine Holdings AG", lei=_LEI)
        assert isinstance(snap, EntitySnapshot)
        assert snap.name == "Alpine Holdings AG"
        assert snap.source == "gleif"

    async def test_returns_none_when_lei_record_not_found(self):
        adapter = _make_adapter(lei_record=None, lei_status=404)
        result = await adapter.fetch("drift-001", "Unknown Corp", lei="NONEXISTENT0000000XY")
        assert result is None

    async def test_returns_none_when_no_lei_and_name_lookup_fails(self):
        adapter = GleifAdapter()
        adapter._lookup_lei_by_name = AsyncMock(return_value=None)
        result = await adapter.fetch("drift-001", "Unknown Corp")
        assert result is None

    async def test_uses_name_lookup_when_no_lei_kwarg(self):
        adapter = GleifAdapter()
        adapter._lookup_lei_by_name = AsyncMock(return_value=_LEI)
        adapter._get_lei_record = AsyncMock(return_value=_LEI_RECORD_ACTIVE)
        adapter._get_parent_lei = AsyncMock(return_value=None)
        adapter._get_children_leis = AsyncMock(return_value=[])
        snap = await adapter.fetch("drift-001", "Alpine Holdings AG")
        adapter._lookup_lei_by_name.assert_awaited_once_with("Alpine Holdings AG")
        assert snap is not None
        assert snap.name == "Alpine Holdings AG"

    async def test_parent_lei_populated_in_beneficial_owners(self):
        adapter = _make_adapter(
            lei_record=_LEI_RECORD_ACTIVE,
            parent=_PARENT_RECORD,
        )
        snap = await adapter.fetch("drift-001", "Alpine Holdings AG", lei=_LEI)
        assert snap is not None
        assert _PARENT_LEI in snap.beneficial_owners

    async def test_children_populated_in_officers(self):
        adapter = _make_adapter(
            lei_record=_LEI_RECORD_ACTIVE,
            children=_CHILDREN_RECORD,
        )
        snap = await adapter.fetch("drift-001", "Alpine Holdings AG", lei=_LEI)
        assert snap is not None
        assert _CHILD_LEI_A in snap.officers
        assert _CHILD_LEI_B in snap.officers

    async def test_annulled_entity_has_dissolved_status(self):
        adapter = _make_adapter(lei_record=_LEI_RECORD_ANNULLED)
        snap = await adapter.fetch("drift-001", "Alpine Holdings AG", lei=_LEI)
        assert snap is not None
        assert snap.dissolution_status == "dissolved"

    async def test_drift_id_propagated_to_snapshot(self):
        adapter = _make_adapter(lei_record=_LEI_RECORD_ACTIVE)
        snap = await adapter.fetch("my-special-drift-id", "Test Corp", lei=_LEI)
        assert snap is not None
        assert snap.drift_id == "my-special-drift-id"


# ---------------------------------------------------------------------------
# GleifAdapter.fetch_signals() — registry diff adapter, returns []
# ---------------------------------------------------------------------------

class TestGleifFetchSignals:
    async def test_returns_empty_list_always(self):
        adapter = GleifAdapter()
        result = await adapter.fetch_signals("drift-001", "Test Corp", lei=_LEI)
        assert result == []

    async def test_returns_empty_list_with_since_month(self):
        adapter = GleifAdapter()
        result = await adapter.fetch_signals("drift-001", "Test Corp", since_month=6, lei=_LEI)
        assert result == []

    async def test_no_network_calls_made(self):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        adapter = GleifAdapter(http_client=mock_client)
        result = await adapter.fetch_signals("drift-001", "Test Corp", lei=_LEI)
        assert result == []
        mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP helpers — _get_lei_record, _get_parent_lei, _get_children_leis
# with a mock httpx.AsyncClient injected directly.
# ---------------------------------------------------------------------------

class TestGleifHttpHelpers:
    def _adapter_with_mock_get(self, side_effect) -> GleifAdapter:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=side_effect)
        return GleifAdapter(http_client=mock_client)

    async def test_get_lei_record_returns_none_on_404(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(404)
        )
        result = await adapter._get_lei_record(_LEI)
        assert result is None

    async def test_get_lei_record_returns_none_on_429(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(429)
        )
        result = await adapter._get_lei_record(_LEI)
        assert result is None

    async def test_get_lei_record_returns_none_on_transport_error(self):
        async def raise_transport(url, **kw):
            raise httpx.TransportError("connection reset")

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = raise_transport
        adapter = GleifAdapter(http_client=mock_client)
        result = await adapter._get_lei_record(_LEI)
        assert result is None

    async def test_get_lei_record_returns_parsed_json_on_200(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, _LEI_RECORD_ACTIVE)
        )
        result = await adapter._get_lei_record(_LEI)
        assert result == _LEI_RECORD_ACTIVE

    async def test_get_parent_lei_returns_none_on_404(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(404)
        )
        result = await adapter._get_parent_lei(_LEI)
        assert result is None

    async def test_get_parent_lei_returns_lei_string_on_200(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, _PARENT_RECORD)
        )
        result = await adapter._get_parent_lei(_LEI)
        assert result == _PARENT_LEI

    async def test_get_parent_lei_returns_none_when_data_empty(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, {"data": None})
        )
        result = await adapter._get_parent_lei(_LEI)
        assert result is None

    async def test_get_children_leis_returns_empty_on_404(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(404)
        )
        result = await adapter._get_children_leis(_LEI)
        assert result == []

    async def test_get_children_leis_returns_lei_list_on_200(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, _CHILDREN_RECORD)
        )
        result = await adapter._get_children_leis(_LEI)
        assert result == [_CHILD_LEI_A, _CHILD_LEI_B]

    async def test_get_children_leis_returns_empty_when_data_empty(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, {"data": []})
        )
        result = await adapter._get_children_leis(_LEI)
        assert result == []

    async def test_lookup_lei_by_name_returns_none_on_failure(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(500)
        )
        result = await adapter._lookup_lei_by_name("Unknown Corp")
        assert result is None

    async def test_lookup_lei_by_name_returns_lei_on_match(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, _NAME_LOOKUP_RESULT)
        )
        result = await adapter._lookup_lei_by_name("Alpine Holdings AG")
        assert result == _LEI

    async def test_lookup_lei_by_name_returns_none_when_no_results(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, {"data": []})
        )
        result = await adapter._lookup_lei_by_name("No Such Company")
        assert result is None

    async def test_transport_error_in_lookup_returns_none(self):
        async def raise_transport(url, **kw):
            raise httpx.TransportError("timeout")

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = raise_transport
        adapter = GleifAdapter(http_client=mock_client)
        result = await adapter._lookup_lei_by_name("Corp")
        assert result is None

    async def test_get_lei_record_returns_none_on_500(self):
        # 5xx errors must be swallowed (same as 404/429) so a GLEIF outage
        # does not propagate as an unhandled exception through the service layer.
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(500)
        )
        result = await adapter._get_lei_record(_LEI)
        assert result is None

    async def test_get_lei_record_returns_none_on_503(self):
        adapter = self._adapter_with_mock_get(
            lambda url, **kw: _mock_response(503)
        )
        result = await adapter._get_lei_record(_LEI)
        assert result is None


# ---------------------------------------------------------------------------
# Integration: EntitySnapshot from fetch() feeds diff_snapshots()
# ---------------------------------------------------------------------------

class TestGleifDiffIntegration:
    """
    Verify that the EntitySnapshot produced by GleifAdapter._normalize()
    produces the correct SnapshotDiff objects when compared to a baseline via
    diff_snapshots(). This validates the full registry-diff signal flow for
    GLEIF without any network I/O.
    """

    def setup_method(self):
        self.adapter = GleifAdapter()

    def test_jurisdiction_unchanged_when_same(self):
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ACTIVE, None, [])
        baseline = _baseline(name="Alpine Holdings AG", jurisdiction="CH")
        diffs = diff_snapshots(baseline, snap)
        # Jurisdiction is the same (CH→CH) — no jurisdiction_changed diff.
        assert not any(d.drift_signal_type == "jurisdiction_changed" for d in diffs)

    def test_annulled_triggers_dissolution_status_changed(self):
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ANNULLED, None, [])
        baseline = _baseline(dissolution_status="active")
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "dissolution_status_changed" in types
        dissolution_diff = next(d for d in diffs if d.drift_signal_type == "dissolution_status_changed")
        assert dissolution_diff.old_value == "active"
        assert dissolution_diff.new_value == "dissolved"
        assert dissolution_diff.severity == pytest.approx(0.90)

    def test_name_change_detected(self):
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ACTIVE, None, [])
        baseline = _baseline(name="Old Corp AG")  # name differs
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "name_changed" in types

    def test_jurisdiction_change_detected(self):
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ACTIVE, None, [])
        baseline = _baseline(jurisdiction="DE")  # was DE, now CH
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "jurisdiction_changed" in types
        jur_diff = next(d for d in diffs if d.drift_signal_type == "jurisdiction_changed")
        assert jur_diff.old_value == "DE"
        assert jur_diff.new_value == "CH"

    def test_new_parent_triggers_ubo_added(self):
        # Baseline: no parent. Current: parent LEI appears.
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ACTIVE, _PARENT_LEI, [])
        baseline = _baseline(beneficial_owners=[])
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "ubo_added" in types
        ubo_diff = next(d for d in diffs if d.drift_signal_type == "ubo_added")
        assert ubo_diff.new_value == _PARENT_LEI

    def test_parent_removal_triggers_ubo_removed(self):
        # Baseline: had parent. Current: no parent.
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ACTIVE, None, [])
        baseline = _baseline(beneficial_owners=[_PARENT_LEI])
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "ubo_removed" in types
        ubo_diff = next(d for d in diffs if d.drift_signal_type == "ubo_removed")
        assert ubo_diff.old_value == _PARENT_LEI

    def test_parent_change_triggers_ubo_added_and_removed(self):
        # Baseline: PARENT_A. Current: PARENT_B.
        old_parent = "OLDPARENT0000000001X"
        new_parent = _PARENT_LEI
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ACTIVE, new_parent, [])
        baseline = _baseline(beneficial_owners=[old_parent])
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "ubo_added" in types
        assert "ubo_removed" in types

    def test_multiple_changes_at_once(self):
        # Name change + dissolution + new parent all detected together.
        snap = self.adapter._normalize("d", _LEI, _LEI_RECORD_ANNULLED, _PARENT_LEI, [])
        baseline = _baseline(name="Old Name Corp", dissolution_status="active", beneficial_owners=[])
        diffs = diff_snapshots(baseline, snap)
        types = {d.drift_signal_type for d in diffs}
        assert "name_changed" in types
        assert "dissolution_status_changed" in types
        assert "ubo_added" in types
