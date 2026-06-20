"""
Tests for the ZEFIX adapter (``app.sources.zefix``).

The HTTP layer is mocked with ``httpx.MockTransport`` so these run fully
offline — no ZEFIX account and no network are required. Payload shapes mirror
the live ZefixPublicREST OpenAPI schema (CompanyShort for search,
CompanyFull[] for the uid lookup; ``legalForm`` is a nested DFIEString map and
``status`` is one of ACTIVE / BEING_CANCELLED / CANCELLED).
"""

from __future__ import annotations

import httpx
import pytest

from app.sources.base import EntitySnapshot
from app.sources.zefix import (
    _STATUS_MAP,
    _best_match,
    _dfie,
    _format_address,
    ZefixAdapter,
)

# --------------------------------------------------------------------------- #
# Fixtures — realistic ZEFIX payloads                                          #
# --------------------------------------------------------------------------- #
_LEGAL_FORM_AG = {
    "id": 3,
    "uid": "0106",
    "name": {"de": "Aktiengesellschaft", "en": "Limited company"},
    "shortName": {"de": "AG", "en": "Ltd"},
}

_COMPANY_FULL = {
    "name": "Helvetia Trading AG",
    "uid": "CHE-123.456.789",
    "ehraid": 1234567,
    "chid": "CH-170.3.000.000-0",
    "legalSeat": "Zug",
    "canton": "ZG",
    "legalForm": _LEGAL_FORM_AG,
    "status": "ACTIVE",
    "sogcDate": "2024-03-15",
    "purpose": "Trading of goods and related services.",
    "address": {
        "street": "Bahnhofstrasse",
        "houseNumber": "1",
        "swissZipCode": "6300",
        "city": "Zug",
    },
    "oldNames": [{"name": "Helvetia Holdings AG", "sequenceNr": 1}],
    "sogcPub": [{"sogcDate": "2024-03-15", "message": "Mutation."}],
}

_COMPANY_SHORT = {
    "name": "Helvetia Trading AG",
    "uid": "CHE-123.456.789",
    "legalSeat": "Zug",
    "legalForm": _LEGAL_FORM_AG,
    "status": "ACTIVE",
}


def _make_adapter(
    handler,
    *,
    username: str = "user",
    password: str = "pass",
    **kwargs,
) -> ZefixAdapter:
    """Build a ZefixAdapter wired to a MockTransport handler."""
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://www.zefix.admin.ch/ZefixPublicREST",
    )
    return ZefixAdapter(
        username=username, password=password, client=client, backoff_base=0.0, **kwargs
    )


def _ok(payload):
    return httpx.Response(200, json=payload)


def _standard_handler(request: httpx.Request) -> httpx.Response:
    """Search -> [CompanyShort]; uid lookup -> [CompanyFull]."""
    if request.url.path.endswith("/company/search"):
        return _ok([_COMPANY_SHORT])
    if "/company/uid/" in request.url.path:
        return _ok([_COMPANY_FULL])
    return httpx.Response(404)


# --------------------------------------------------------------------------- #
# Pure helpers                                                                 #
# --------------------------------------------------------------------------- #
class TestHelpers:
    def test_dfie_prefers_german_then_falls_back(self):
        assert _dfie({"de": "AG", "en": "Ltd"}) == "AG"
        assert _dfie({"en": "Ltd"}) == "Ltd"  # de missing → next preference
        assert _dfie({"fr": "SA"}) == "SA"  # only an off-preference language
        assert _dfie({}) is None
        assert _dfie(None) is None
        assert _dfie("AG") == "AG"  # already a plain string

    def test_best_match_picks_closest_above_threshold(self):
        cands = [{"name": "Helvetia Trading AG"}, {"name": "Totally Other GmbH"}]
        assert _best_match("Helvetia Trading", cands)["name"] == "Helvetia Trading AG"

    def test_best_match_returns_none_when_all_weak(self):
        assert _best_match("Helvetia Trading AG", [{"name": "ZZZ"}]) is None

    def test_best_match_ignores_nameless_candidates(self):
        assert _best_match("Helvetia", [{"uid": "x"}, {"name": "Helvetia"}]) is not None

    def test_format_address_builds_one_line(self):
        line = _format_address(_COMPANY_FULL["address"], "Zug")
        assert line == "Bahnhofstrasse 1, 6300 Zug"

    def test_format_address_falls_back_to_legal_seat(self):
        assert _format_address(None, "Zug") == "Zug"
        assert _format_address(None, None) is None

    def test_format_address_coerces_numeric_fields(self):
        # Live ZEFIX may serialise ZIP / house number as ints — must not raise.
        addr = {"street": "Bahnhofstrasse", "houseNumber": 1, "swissZipCode": 6300, "city": "Zug"}
        assert _format_address(addr, "Zug") == "Bahnhofstrasse 1, 6300 Zug"

    def test_best_match_skips_non_dict_elements(self):
        # A malformed payload element must degrade, not raise AttributeError.
        assert _best_match("Helvetia", ["junk", None, {"name": "Helvetia"}]) is not None
        assert _best_match("Helvetia", ["junk", None]) is None

    def test_status_map_covers_live_vocabulary(self):
        assert _STATUS_MAP == {
            "ACTIVE": "active",
            "BEING_CANCELLED": "dissolved",
            "CANCELLED": "struck_off",
        }


# --------------------------------------------------------------------------- #
# fetch()                                                                      #
# --------------------------------------------------------------------------- #
class TestFetch:
    async def test_happy_path_maps_all_fields(self):
        snap = await _make_adapter(_standard_handler).fetch("drift-001", "Helvetia Trading")
        assert snap is not None
        assert snap.drift_id == "drift-001"
        assert snap.source == "zefix"
        assert snap.name == "Helvetia Trading AG"
        assert snap.legal_form == "AG"  # shortName.de
        assert snap.jurisdiction == "ZG"  # canton, not country
        assert snap.registered_address == "Bahnhofstrasse 1, 6300 Zug"
        assert snap.dissolution_status == "active"
        # ZEFIX never exposes ownership/officers.
        assert snap.beneficial_owners == []
        assert snap.officers == []
        # Raw payload preserved for downstream use.
        assert snap.raw_data["uid"] == "CHE-123.456.789"
        assert snap.raw_data["country"] == "CH"
        assert snap.raw_data["canton"] == "ZG"
        assert snap.raw_data["legal_seat"] == "Zug"
        assert snap.raw_data["purpose"].startswith("Trading")
        assert snap.raw_data["old_names"] == ["Helvetia Holdings AG"]
        assert snap.raw_data["mutation_date"] == "2024-03-15"

    async def test_no_credentials_returns_none_without_http(self):
        def explode(request):  # pragma: no cover - must never be called
            raise AssertionError("HTTP must not be attempted without credentials")

        adapter = _make_adapter(explode, username="", password="")
        assert await adapter.fetch("drift-001", "Helvetia") is None

    async def test_no_match_returns_none(self):
        def handler(request):
            if request.url.path.endswith("/company/search"):
                return _ok([{"name": "Completely Unrelated SA", "uid": "CHE-999"}])
            return httpx.Response(404)

        assert await _make_adapter(handler).fetch("d", "Helvetia Trading AG") is None

    async def test_empty_search_returns_none(self):
        adapter = _make_adapter(lambda r: _ok([]))
        assert await adapter.fetch("d", "Helvetia") is None

    async def test_picks_best_record_among_multiple_uid_results(self):
        branch = {**_COMPANY_FULL, "name": "Helvetia Trading AG, Branch Geneva", "canton": "GE"}
        def handler(request):
            if request.url.path.endswith("/company/search"):
                return _ok([_COMPANY_SHORT])
            return _ok([branch, _COMPANY_FULL])  # head office is second

        snap = await _make_adapter(handler).fetch("d", "Helvetia Trading AG")
        assert snap.jurisdiction == "ZG"  # matched the head office, not the branch

    async def test_retries_on_429_then_succeeds(self):
        calls = {"search": 0}

        def handler(request):
            if request.url.path.endswith("/company/search"):
                calls["search"] += 1
                if calls["search"] == 1:
                    return httpx.Response(429)
                return _ok([_COMPANY_SHORT])
            return _ok([_COMPANY_FULL])

        snap = await _make_adapter(handler).fetch("d", "Helvetia Trading")
        assert snap is not None
        assert calls["search"] == 2  # first 429 was retried

    async def test_http_error_propagates_when_credentialed(self):
        adapter = _make_adapter(lambda r: httpx.Response(500))
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.fetch("d", "Helvetia")

    async def test_retry_exhaustion_raises(self):
        # Every attempt returns 429 → after the retries are spent the final
        # raise_for_status surfaces the error rather than looping forever.
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(429)

        adapter = _make_adapter(handler, max_retries=3)
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.fetch("d", "Helvetia")
        assert calls["n"] == 3  # exhausted exactly max_retries attempts

    async def test_uid_kwarg_skips_search(self):
        # Passing uid= must go straight to the uid endpoint, never hitting search.
        def handler(request):
            if request.url.path.endswith("/company/search"):  # pragma: no cover
                raise AssertionError("search must be skipped when uid= is given")
            assert request.url.path.endswith("/company/uid/CHE-123.456.789")
            return _ok([_COMPANY_FULL])

        snap = await _make_adapter(handler).fetch("d", "ignored", uid="CHE-123.456.789")
        assert snap is not None and snap.raw_data["uid"] == "CHE-123.456.789"


# --------------------------------------------------------------------------- #
# fetch_signals()                                                             #
# --------------------------------------------------------------------------- #
def _baseline() -> EntitySnapshot:
    return EntitySnapshot(
        drift_id="drift-001",
        name="Helvetia Holdings AG",
        source="zefix",
        legal_form="GmbH",
        jurisdiction="ZH",
        dissolution_status="active",
        raw_data={"uid": "CHE-123.456.789"},
    )


def _current(**overrides) -> EntitySnapshot:
    base = dict(
        drift_id="drift-001",
        name="Helvetia Trading AG",
        source="zefix",
        legal_form="AG",
        jurisdiction="ZG",
        dissolution_status="active",
        raw_data={"uid": "CHE-123.456.789"},
    )
    base.update(overrides)
    return EntitySnapshot(**base)


class TestFetchSignals:
    async def test_no_credentials_still_diffs_injected_snapshots(self):
        # Diffing two caller-supplied snapshots is pure compute — it must work
        # even with no account configured (no network/auth needed).
        adapter = ZefixAdapter(username="", password="")
        signals = await adapter.fetch_signals(
            "drift-001", "Helvetia", baseline=_baseline(), current=_current()
        )
        assert {s.signal_type for s in signals} == {
            "name_change", "legal_form_change", "jurisdiction_change"
        }

    async def test_no_credentials_and_no_snapshot_returns_empty(self):
        # Without creds AND without an injected snapshot there is nothing to do.
        adapter = ZefixAdapter(username="", password="")
        assert await adapter.fetch_signals("d", "Helvetia") == []

    async def test_diff_against_baseline_emits_mapped_signals(self):
        adapter = ZefixAdapter(username="u", password="p")
        signals = await adapter.fetch_signals(
            "drift-001", "Helvetia Trading AG", since_month=7,
            baseline=_baseline(), current=_current(),
        )
        by_type = {s.signal_type: s for s in signals}
        assert set(by_type) == {"name_change", "legal_form_change", "jurisdiction_change"}
        # Severities come straight from the diff layer (floats in [0,1]).
        assert by_type["jurisdiction_change"].severity == pytest.approx(0.80)
        assert by_type["name_change"].severity == pytest.approx(0.70)
        assert by_type["legal_form_change"].severity == pytest.approx(0.65)
        # Provenance + temporal alignment.
        for s in signals:
            assert s.source == "ZEFIX"
            assert s.month == 7
            assert s.source_url and "CHE-123.456.789" in s.source_url

    async def test_unchanged_entity_emits_no_signals(self):
        adapter = ZefixAdapter(username="u", password="p")
        signals = await adapter.fetch_signals(
            "d", "Helvetia", baseline=_current(), current=_current()
        )
        assert signals == []

    async def test_terminal_status_without_baseline_is_adverse(self):
        adapter = ZefixAdapter(username="u", password="p")
        signals = await adapter.fetch_signals(
            "d", "Helvetia", current=_current(dissolution_status="struck_off")
        )
        assert len(signals) == 1
        assert signals[0].signal_type == "status_change"
        assert signals[0].severity == pytest.approx(0.90)

    async def test_active_status_without_baseline_is_silent(self):
        adapter = ZefixAdapter(username="u", password="p")
        signals = await adapter.fetch_signals("d", "Helvetia", current=_current())
        assert signals == []

    async def test_dissolution_diff_maps_to_status_change(self):
        adapter = ZefixAdapter(username="u", password="p")
        signals = await adapter.fetch_signals(
            "d", "Helvetia",
            baseline=_current(),
            current=_current(dissolution_status="struck_off"),
        )
        assert [s.signal_type for s in signals] == ["status_change"]

    async def test_fetches_current_when_not_injected(self):
        adapter = _make_adapter(_standard_handler)
        # No `current=` → adapter calls fetch() itself; no baseline, active status
        # → silent. Proves the fetch path is exercised end to end.
        assert await adapter.fetch_signals("d", "Helvetia Trading") == []
