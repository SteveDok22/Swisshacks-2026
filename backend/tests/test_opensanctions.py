"""
Tests for the OpenSanctions adapter (``app.sources.opensanctions``).

The HTTP layer is mocked with ``httpx.MockTransport`` so these run fully
offline — no API key and no network are required. Payload shapes mirror the
live OpenSanctions yente API (``GET /search/default?q=...``, ``results[]``
with ``id``, ``caption``, ``score`` fields).
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.sources.opensanctions import (
    _SEVERITY_CRITICAL,
    _SEVERITY_HIGH,
    _SEVERITY_UBO_CRITICAL,
    _SEVERITY_UBO_HIGH,
    _THRESHOLD_HIGH,
    _THRESHOLD_LOW,
    OpenSanctionsAdapter,
)

# --------------------------------------------------------------------------- #
# Helpers — mock transport                                                      #
# --------------------------------------------------------------------------- #

def _response(payload: dict | list, *, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def _make_adapter(
    handler,
    *,
    api_key: str = "",
    max_retries: int = 3,
    backoff_base: float = 0.0,
) -> OpenSanctionsAdapter:
    """Build an adapter wired to a MockTransport handler (no real network).

    The client is injected so the adapter does not own it — ``aclose()`` will
    not close it, which is the correct behaviour for tests.
    """
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.opensanctions.org",
    )
    return OpenSanctionsAdapter(
        api_key=api_key,
        client=client,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )


def _hit(
    entity_id: str = "ofac-abc",
    caption: str = "Evil Corp AG",
    score: float = 0.92,
) -> dict:
    return {"id": entity_id, "caption": caption, "score": score, "schema": "Company"}


def _results(*hits) -> dict:
    return {"results": list(hits), "query": {}, "total": {"value": len(hits)}}


def _standard_handler(results: list[dict]):
    """Factory: returns a handler that always returns the given results list."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/search/" in request.url.path
        return _response({"results": results})
    return handler


# --------------------------------------------------------------------------- #
# Module-level constants                                                        #
# --------------------------------------------------------------------------- #

class TestConstants:
    def test_threshold_ordering(self):
        assert 0.0 < _THRESHOLD_LOW < _THRESHOLD_HIGH < 1.0

    def test_severity_ordering(self):
        # Definitive hits should be more severe than probable hits.
        assert _SEVERITY_HIGH < _SEVERITY_CRITICAL
        assert _SEVERITY_UBO_HIGH < _SEVERITY_UBO_CRITICAL

    def test_direct_hits_more_severe_than_ubo(self):
        # A direct sanctions match is more severe than a UBO match.
        assert _SEVERITY_UBO_CRITICAL < _SEVERITY_CRITICAL
        assert _SEVERITY_UBO_HIGH <= _SEVERITY_HIGH


# --------------------------------------------------------------------------- #
# record_url                                                                   #
# --------------------------------------------------------------------------- #

class TestRecordUrl:
    def test_known_id(self):
        adapter = OpenSanctionsAdapter(api_key="")
        url = adapter.record_url("ofac-abc123")
        assert url == "https://www.opensanctions.org/entities/ofac-abc123/"

    def test_empty_id_returns_none(self):
        adapter = OpenSanctionsAdapter(api_key="")
        assert adapter.record_url("") is None


# --------------------------------------------------------------------------- #
# Auth header                                                                  #
# --------------------------------------------------------------------------- #

class TestAuthHeaders:
    def test_no_key_gives_empty_headers(self):
        adapter = OpenSanctionsAdapter(api_key="")
        assert adapter._auth_headers == {}

    def test_api_key_becomes_authorization_header(self):
        adapter = OpenSanctionsAdapter(api_key="test-key-123")
        assert adapter._auth_headers == {"Authorization": "ApiKey test-key-123"}


# --------------------------------------------------------------------------- #
# fetch() — always None                                                        #
# --------------------------------------------------------------------------- #

class TestFetch:
    async def test_fetch_always_returns_none(self):
        adapter = _make_adapter(lambda r: _response({}))
        result = await adapter.fetch("drift-001", "Evil Corp AG")
        assert result is None

    async def test_fetch_no_network_call(self):
        """fetch() must not touch the network (it's a screening-only source)."""
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            calls.append(1)
            return _response({})

        adapter = _make_adapter(handler)
        await adapter.fetch("drift-001", "Any Name")
        assert calls == [], "fetch() must not make HTTP calls"


# --------------------------------------------------------------------------- #
# fetch_signals() — main entity screening                                      #
# --------------------------------------------------------------------------- #

class TestFetchSignalsMainEntity:
    async def test_no_results_returns_empty(self):
        adapter = _make_adapter(_standard_handler([]))
        signals = await adapter.fetch_signals("drift-001", "Clean Corp AG")
        assert signals == []

    async def test_high_score_hit_emits_critical_sanctions_signal(self):
        hit = _hit(score=0.92)
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("drift-001", "Evil Corp AG", since_month=5)

        assert len(signals) == 1
        sig = signals[0]
        assert sig.signal_type == "sanctions"
        assert sig.severity == pytest.approx(_SEVERITY_CRITICAL)
        assert sig.month == 5
        assert sig.source == "OpenSanctions"
        assert "Evil Corp AG" in sig.headline
        assert "0.92" in sig.headline
        assert sig.source_url == "https://www.opensanctions.org/entities/ofac-abc/"

    async def test_probable_hit_emits_high_sanctions_signal(self):
        hit = _hit(score=0.78)
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("drift-001", "Ambiguous Corp", since_month=3)

        assert len(signals) == 1
        sig = signals[0]
        assert sig.signal_type == "sanctions"
        assert sig.severity == pytest.approx(_SEVERITY_HIGH)
        assert "manual confirmation" in sig.headline
        assert "0.78" in sig.headline

    async def test_score_at_threshold_high_is_critical(self):
        hit = _hit(score=_THRESHOLD_HIGH)
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals[0].severity == pytest.approx(_SEVERITY_CRITICAL)

    async def test_score_just_below_threshold_high_is_high(self):
        hit = _hit(score=_THRESHOLD_HIGH - 0.01)
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals[0].severity == pytest.approx(_SEVERITY_HIGH)

    async def test_score_below_low_threshold_is_filtered(self):
        hit = _hit(score=_THRESHOLD_LOW - 0.01)
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals == []

    async def test_score_at_low_threshold_is_included(self):
        hit = _hit(score=_THRESHOLD_LOW)
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("d", "Corp")
        assert len(signals) == 1

    async def test_multiple_hits_all_emitted(self):
        hits = [_hit(score=0.95), _hit(score=0.72, entity_id="eu-xyz"), _hit(score=0.50)]
        adapter = _make_adapter(_standard_handler(hits))
        signals = await adapter.fetch_signals("d", "Corp")
        # Third hit (0.50) is below threshold — only two signals.
        assert len(signals) == 2
        types = {s.signal_type for s in signals}
        assert types == {"sanctions"}

    async def test_since_month_stamped_on_signal(self):
        adapter = _make_adapter(_standard_handler([_hit()]))
        signals = await adapter.fetch_signals("d", "Corp", since_month=9)
        assert signals[0].month == 9

    async def test_no_api_key_still_calls_api(self):
        """Without a key the adapter should still attempt unauthenticated access."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.headers.get("Authorization", "none"))
            return _response({"results": []})

        adapter = _make_adapter(handler, api_key="")
        await adapter.fetch_signals("d", "Corp")
        assert len(calls) == 1
        assert calls[0] == "none"

    async def test_api_key_sent_in_auth_header(self):
        headers_seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            headers_seen.append(request.headers.get("Authorization", ""))
            return _response({"results": []})

        adapter = _make_adapter(handler, api_key="my-secret-key")
        await adapter.fetch_signals("d", "Corp")
        assert headers_seen[0] == "ApiKey my-secret-key"

    async def test_schema_company_sent_in_request(self):
        params_seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            params_seen.append(str(request.url.params.get("schema", "")))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "Corp")
        assert params_seen[0] == "Company"

    async def test_entity_name_in_query_param(self):
        q_seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            q_seen.append(request.url.params.get("q", ""))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "Specific Corp AG")
        assert q_seen[0] == "Specific Corp AG"

    async def test_hit_with_no_caption_uses_name(self):
        hit = {"id": "x", "score": 0.92}  # no caption
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("d", "FallbackName Corp")
        assert "FallbackName Corp" in signals[0].headline

    async def test_hit_with_no_id_has_no_source_url(self):
        hit = {"caption": "Corp", "score": 0.92}  # no id
        adapter = _make_adapter(_standard_handler([hit]))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals[0].source_url is None


# --------------------------------------------------------------------------- #
# fetch_signals() — UBO chain screening                                        #
# --------------------------------------------------------------------------- #

class TestFetchSignalsUboScreening:
    async def test_ubo_high_score_emits_ownership_change(self):
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("q", "")
            calls.append(q)
            if q == "Clean Corp":
                return _response({"results": []})
            if q == "Dirty UBO":
                return _response({"results": [_hit(score=0.91, entity_id="un-xyz", caption="Dirty UBO")]})
            return _response({"results": []})

        adapter = _make_adapter(handler)
        signals = await adapter.fetch_signals(
            "d", "Clean Corp", ubo_names=["Dirty UBO"]
        )

        assert len(signals) == 1
        sig = signals[0]
        assert sig.signal_type == "ownership_change"
        assert sig.severity == pytest.approx(_SEVERITY_UBO_CRITICAL)
        assert "Dirty UBO" in sig.headline
        assert "UBO" in sig.headline
        assert sig.source_url == "https://www.opensanctions.org/entities/un-xyz/"

    async def test_ubo_probable_hit_uses_lower_severity(self):
        def handler(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("q", "")
            if q == "Partial UBO":
                return _response({"results": [_hit(score=0.76, caption="Partial UBO")]})
            return _response({"results": []})

        adapter = _make_adapter(handler)
        signals = await adapter.fetch_signals("d", "Entity", ubo_names=["Partial UBO"])
        assert signals[0].severity == pytest.approx(_SEVERITY_UBO_HIGH)
        assert "probable match" in signals[0].headline

    async def test_ubo_below_threshold_filtered(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _response({"results": [_hit(score=0.60)]})

        adapter = _make_adapter(handler)
        signals = await adapter.fetch_signals("d", "Entity", ubo_names=["Low Score UBO"])
        assert signals == []

    async def test_multiple_ubos_all_screened(self):
        screened: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            screened.append(request.url.params.get("q", ""))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "Entity", ubo_names=["UBO1", "UBO2", "UBO3"])
        # Main entity + 3 UBOs = 4 calls
        assert "Entity" in screened
        assert "UBO1" in screened
        assert "UBO2" in screened
        assert "UBO3" in screened

    async def test_ubo_screening_no_schema_filter(self):
        """UBO searches must NOT restrict to Company schema — UBOs can be persons."""
        schemas_seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("q", "")
            if q != "MainEntity":
                schemas_seen.append(request.url.params.get("schema", ""))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "MainEntity", ubo_names=["Some Person"])
        assert schemas_seen == [""]  # no schema param for UBO calls

    async def test_empty_ubo_names_list_no_extra_calls(self):
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "Entity", ubo_names=[])
        assert len(calls) == 1  # only the main entity call

    async def test_none_ubo_names_treated_as_empty(self):
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "Entity", ubo_names=None)
        assert len(calls) == 1

    async def test_empty_string_ubo_name_skipped(self):
        """Empty string in ubo_names must not trigger an extra API call."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.params.get("q", ""))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter.fetch_signals("d", "Entity", ubo_names=["", "ValidUBO"])
        assert "" not in calls

    async def test_ubo_and_main_entity_signals_combined(self):
        def handler(request: httpx.Request) -> httpx.Response:
            # Both the main entity and the UBO are sanctioned.
            return _response({"results": [_hit(score=0.90)]})

        adapter = _make_adapter(handler)
        signals = await adapter.fetch_signals("d", "Bad Corp", ubo_names=["Bad Person"])
        assert len(signals) == 2
        types = {s.signal_type for s in signals}
        assert "sanctions" in types
        assert "ownership_change" in types


# --------------------------------------------------------------------------- #
# Error handling / resilience                                                  #
# --------------------------------------------------------------------------- #

class TestErrorHandling:
    async def test_transport_error_returns_empty(self):
        """A network-level failure must not propagate — return []."""
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        adapter = _make_adapter(handler)
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals == []

    async def test_http_error_returns_empty(self):
        """A non-retryable HTTP error (500) must return [] via graceful handling."""
        adapter = _make_adapter(lambda r: httpx.Response(500))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals == []

    async def test_404_returns_empty(self):
        adapter = _make_adapter(lambda r: httpx.Response(404))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals == []

    async def test_429_retries_then_succeeds(self):
        calls: dict[str, int] = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 2:
                return httpx.Response(429)
            return _response({"results": [_hit(score=0.92)]})

        adapter = _make_adapter(handler, max_retries=3)
        signals = await adapter.fetch_signals("d", "Corp")
        assert len(signals) == 1
        assert calls["n"] == 2

    async def test_429_exhaustion_returns_empty(self):
        """All retries spent on 429 — must return [] not crash."""
        adapter = _make_adapter(lambda r: httpx.Response(429), max_retries=2)
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals == []

    async def test_ubo_http_error_skips_that_ubo_continues(self):
        """An HTTP error on one UBO must not abort screening of subsequent UBOs."""
        call_order: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("q", "")
            call_order.append(q)
            if q == "BadUBO":
                return httpx.Response(500)
            return _response({"results": []})

        adapter = _make_adapter(handler)
        signals = await adapter.fetch_signals(
            "d", "MainEntity", ubo_names=["BadUBO", "GoodUBO"]
        )
        # Both UBOs were attempted; the error on BadUBO was skipped.
        assert "BadUBO" in call_order
        assert "GoodUBO" in call_order
        assert signals == []  # no clean hits above threshold

    async def test_empty_results_key_in_payload(self):
        """Payload with no 'results' key must return []."""
        adapter = _make_adapter(lambda r: _response({}))
        signals = await adapter.fetch_signals("d", "Corp")
        assert signals == []


# --------------------------------------------------------------------------- #
# _search() — low-level HTTP helper                                             #
# --------------------------------------------------------------------------- #

class TestSearchHelper:
    async def test_returns_results_list(self):
        hits = [_hit(score=0.90), _hit(score=0.75, entity_id="eu-xyz")]
        adapter = _make_adapter(_standard_handler(hits))
        results = await adapter._search("Corp")
        assert results == hits

    async def test_empty_results_returns_empty_list(self):
        adapter = _make_adapter(_standard_handler([]))
        assert await adapter._search("Corp") == []

    async def test_transport_error_returns_empty(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        adapter = _make_adapter(handler)
        assert await adapter._search("Corp") == []

    async def test_http_error_propagates(self):
        """_search raises HTTPStatusError on non-retryable failures."""
        adapter = _make_adapter(lambda r: httpx.Response(500))
        with pytest.raises(httpx.HTTPStatusError):
            await adapter._search("Corp")

    async def test_schema_param_included_when_given(self):
        params_seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            params_seen.append(dict(request.url.params))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter._search("Corp", schema="Company")
        assert params_seen[0]["schema"] == "Company"

    async def test_schema_param_absent_when_not_given(self):
        params_seen: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            params_seen.append(dict(request.url.params))
            return _response({"results": []})

        adapter = _make_adapter(handler)
        await adapter._search("Corp")
        assert "schema" not in params_seen[0]

    async def test_retry_count_respects_max_retries(self):
        calls: dict[str, int] = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(429)

        adapter = _make_adapter(handler, max_retries=3)
        with pytest.raises(httpx.HTTPStatusError):
            await adapter._search("Corp")
        assert calls["n"] == 3


# --------------------------------------------------------------------------- #
# Signal factory methods (pure — no I/O)                                       #
# --------------------------------------------------------------------------- #

class TestSignalFactories:
    def _adapter(self) -> OpenSanctionsAdapter:
        return OpenSanctionsAdapter(api_key="")

    def test_sanctions_signal_definitive_hit(self):
        adapter = self._adapter()
        sig = adapter._sanctions_signal(
            caption="Evil Corp", score=0.92, entity_id="ofac-abc", month=7
        )
        assert sig.signal_type == "sanctions"
        assert sig.severity == pytest.approx(_SEVERITY_CRITICAL)
        assert "Sanctions match" in sig.headline
        assert "0.92" in sig.headline
        assert sig.source_url == "https://www.opensanctions.org/entities/ofac-abc/"

    def test_sanctions_signal_probable_hit(self):
        adapter = self._adapter()
        sig = adapter._sanctions_signal(
            caption="Ambiguous Corp", score=0.78, entity_id="eu-xyz", month=4
        )
        assert sig.severity == pytest.approx(_SEVERITY_HIGH)
        assert "manual confirmation" in sig.headline
        assert "0.78" in sig.headline

    def test_ubo_signal_definitive(self):
        adapter = self._adapter()
        sig = adapter._ubo_signal(
            ubo_name="Alice Holdings",
            caption="Alice Holdings Ltd",
            score=0.91,
            entity_id="un-abc",
            month=3,
        )
        assert sig.signal_type == "ownership_change"
        assert sig.severity == pytest.approx(_SEVERITY_UBO_CRITICAL)
        assert "Alice Holdings" in sig.headline
        assert "match" in sig.headline
        assert "probable" not in sig.headline

    def test_ubo_signal_probable(self):
        adapter = self._adapter()
        sig = adapter._ubo_signal(
            ubo_name="Bob Person",
            caption="Bob Person Jr",
            score=0.73,
            entity_id="eu-bob",
            month=2,
        )
        assert sig.severity == pytest.approx(_SEVERITY_UBO_HIGH)
        assert "probable match" in sig.headline

    def test_signal_headline_truncated_to_200_chars(self):
        adapter = self._adapter()
        long_caption = "A" * 250
        sig = adapter._sanctions_signal(
            caption=long_caption, score=0.92, entity_id="x", month=0
        )
        assert len(sig.headline) <= 200
        assert sig.headline.startswith("Sanctions match:")

    def test_signal_severity_in_valid_range(self):
        adapter = self._adapter()
        for score in (0.70, 0.80, 0.85, 0.92, 1.0):
            sig = adapter._sanctions_signal(
                caption="Corp", score=score, entity_id="x", month=0
            )
            assert 0.0 <= sig.severity <= 1.0


# --------------------------------------------------------------------------- #
# CostMixin / metadata contract                                                 #
# --------------------------------------------------------------------------- #

class TestClientLifecycle:
    def test_injected_client_not_owned(self):
        client = httpx.AsyncClient(base_url="https://api.opensanctions.org")
        adapter = OpenSanctionsAdapter(api_key="", client=client)
        assert adapter._http is client
        assert adapter._owns_client is False

    async def test_no_injected_client_is_owned(self):
        adapter = OpenSanctionsAdapter(api_key="")
        assert adapter._owns_client is True
        await adapter.aclose()

    async def test_aclose_does_not_close_injected_client(self):
        """An injected client must remain usable after aclose()."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": []})),
            base_url="https://api.opensanctions.org",
        )
        adapter = OpenSanctionsAdapter(api_key="", client=mock_client)
        await adapter.aclose()
        # The injected client must still be open (not closed by the adapter).
        assert not mock_client.is_closed

    async def test_context_manager_closes_owned_client(self):
        """Using adapter as an async context manager closes its own client."""
        adapter = OpenSanctionsAdapter(api_key="")
        assert adapter._owns_client is True
        async with adapter:
            pass
        assert adapter._http.is_closed


class TestAdapterMetadata:
    def test_source_name(self):
        assert OpenSanctionsAdapter.source_name == "opensanctions"

    def test_is_usable(self):
        # FREEMIUM + PLANNED → usable (not skipped).
        assert OpenSanctionsAdapter.is_usable()
        assert not OpenSanctionsAdapter.is_skipped()

    def test_use_cases(self):
        assert 2 in OpenSanctionsAdapter.use_cases
        assert 5 in OpenSanctionsAdapter.use_cases

    def test_signal_types(self):
        assert "sanctions" in OpenSanctionsAdapter.signal_types
        assert "ownership_change" in OpenSanctionsAdapter.signal_types

    def test_repr_does_not_crash(self):
        adapter = OpenSanctionsAdapter(api_key="")
        assert "opensanctions" in repr(adapter)
