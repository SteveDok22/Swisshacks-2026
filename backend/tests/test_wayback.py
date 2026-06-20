"""
Tests for app/sources/wayback.py — WaybackAdapter implementation.

Covers:
- Adapter metadata (cost, status, signal_types, use_cases)
- Pure helpers: _html_to_text, _name_to_domain, _TextExtractor
- fetch() with mocked internal helpers: happy path, no snapshot, transport
  errors, domain kwarg preference, onboarding_date forwarding, polite delay,
  text truncation, raw_data structure
- fetch_signals() always returns []
- record_url() formats correctly
- HTTP helpers: _find_snapshot and _fetch_text with representative status codes
  and transport errors
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.sources.base import EntitySnapshot
from app.sources.cost import AdapterStatus, SourceCost
from app.sources.wayback import (
    WaybackAdapter,
    _ALLOWED_SNAPSHOT_PREFIX,
    _MAX_TEXT_CHARS,
    _POLITE_DELAY_S,
    _html_to_text,
    _name_to_domain,
)


# ---------------------------------------------------------------------------
# Shared sample data — representative Wayback API responses
# ---------------------------------------------------------------------------

_DOMAIN = "example.com"
_TIMESTAMP = "20210315120000"
_SNAPSHOT_URL = f"https://web.archive.org/web/{_TIMESTAMP}/{_DOMAIN}"

_AVAILABILITY_FOUND = {
    "url": _DOMAIN,
    "archived_snapshots": {
        "closest": {
            "available": True,
            "url": _SNAPSHOT_URL,
            "timestamp": _TIMESTAMP,
            "status": "200",
        }
    },
}

_AVAILABILITY_NOT_FOUND = {
    "url": _DOMAIN,
    "archived_snapshots": {},
}

_SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Example Corp</title><style>body { color: red }</style></head>
<body>
  <nav>Navigation menu</nav>
  <main>
    <h1>Welcome to Example Corp</h1>
    <p>We are a boutique consultancy specialising in financial services.</p>
    <p>Contact us at info@example.com</p>
  </main>
  <script>alert('xss')</script>
  <footer>Footer content</footer>
</body>
</html>
"""

_EXPECTED_TEXT_FRAGMENT = "Welcome to Example Corp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(
    status_code: int,
    payload: dict | None = None,
    text: str = "",
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json = MagicMock(return_value=payload or {})
    resp.text = text
    return resp


def _adapter_with_mock_get(side_effect) -> WaybackAdapter:
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=side_effect)
    return WaybackAdapter(http_client=mock_client)


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------

class TestWaybackMetadata:
    def test_source_name(self):
        assert WaybackAdapter.source_name == "wayback"

    def test_cost_is_free(self):
        assert WaybackAdapter.cost is SourceCost.FREE

    def test_status_is_planned(self):
        assert WaybackAdapter.status is AdapterStatus.PLANNED

    def test_requires_no_api_key(self):
        assert WaybackAdapter.requires_api_key is False

    def test_use_cases_match_roadmap(self):
        assert set(WaybackAdapter.use_cases) == {9, 10}

    def test_signal_types_declared(self):
        assert set(WaybackAdapter.signal_types) == {"business_model_change", "domain_change"}

    def test_is_usable(self):
        assert WaybackAdapter.is_usable() is True

    def test_is_not_skipped(self):
        assert WaybackAdapter.is_skipped() is False

    def test_is_free(self):
        assert WaybackAdapter.is_free() is True

    def test_record_url_contains_domain(self):
        url = WaybackAdapter().record_url(_DOMAIN)
        assert _DOMAIN in url
        assert url.startswith("https://web.archive.org")

    async def test_aclose_does_not_raise(self):
        adapter = WaybackAdapter()
        await adapter.aclose()

    async def test_async_context_manager_does_not_close_injected_client(self):
        closed: list[bool] = []
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock(side_effect=lambda: closed.append(True))
        async with WaybackAdapter(http_client=mock_client):
            pass
        # Injected client is never closed by the adapter.
        assert closed == []


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHtmlToText:
    def test_extracts_body_text(self):
        text = _html_to_text(_SAMPLE_HTML)
        assert _EXPECTED_TEXT_FRAGMENT in text

    def test_strips_script_tags(self):
        html = "<html><body><script>alert('xss')</script><p>Good</p></body></html>"
        text = _html_to_text(html)
        assert "alert" not in text
        assert "Good" in text

    def test_strips_style_tags(self):
        html = "<html><head><style>.cls{color:red}</style></head><body><p>Text</p></body></html>"
        text = _html_to_text(html)
        assert ".cls" not in text
        assert "Text" in text

    def test_strips_nav_and_footer(self):
        text = _html_to_text(_SAMPLE_HTML)
        assert "Navigation menu" not in text
        assert "Footer content" not in text

    def test_collapses_whitespace(self):
        text = _html_to_text("<p>  Too   many   spaces  </p>")
        assert "  " not in text

    def test_empty_html_returns_empty_string(self):
        assert _html_to_text("") == ""

    def test_plain_text_passthrough(self):
        assert _html_to_text("Hello World") == "Hello World"

    def test_nested_skip_tags_depth_tracked(self):
        # Nested <nav> inside <nav> — content should still be stripped.
        html = "<nav><nav>Inner nav</nav></nav><p>Body</p>"
        text = _html_to_text(html)
        assert "Inner nav" not in text
        assert "Body" in text


class TestNameToDomain:
    def test_simple_name(self):
        assert _name_to_domain("Example Corp") == "example-corp.com"

    def test_special_characters_replaced(self):
        domain = _name_to_domain("Acme & Co. Ltd!")
        assert " " not in domain
        assert "&" not in domain

    def test_lowercase(self):
        upper = _name_to_domain("UPPER CASE AG")
        lower = _name_to_domain("upper case ag")
        assert upper == lower

    def test_ends_with_dot_com(self):
        assert _name_to_domain("Anything").endswith(".com")

    def test_consecutive_special_chars_merged(self):
        domain = _name_to_domain("A  --  B")
        assert "--" not in domain


# ---------------------------------------------------------------------------
# WaybackAdapter.fetch() — mocked internal helpers
# ---------------------------------------------------------------------------

class TestWaybackFetch:
    async def test_happy_path_returns_entity_snapshot(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(_SNAPSHOT_URL, _TIMESTAMP))
        adapter._fetch_text = AsyncMock(return_value="We are a consultancy.")
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock):
            snap = await adapter.fetch("drift-001", "Example Corp", domain=_DOMAIN)
        assert isinstance(snap, EntitySnapshot)
        assert snap.source == "wayback"
        assert snap.drift_id == "drift-001"
        assert snap.name == "Example Corp"

    async def test_raw_data_contains_all_fields(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(_SNAPSHOT_URL, _TIMESTAMP))
        adapter._fetch_text = AsyncMock(return_value="Some text")
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock):
            snap = await adapter.fetch("drift-001", "Example Corp", domain=_DOMAIN)
        assert snap is not None
        assert snap.raw_data["snapshot_url"] == _SNAPSHOT_URL
        assert snap.raw_data["snapshot_date"] == _TIMESTAMP
        assert snap.raw_data["domain"] == _DOMAIN
        assert snap.raw_data["website_text"] == "Some text"

    async def test_returns_none_when_no_snapshot_found(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(None, None))
        snap = await adapter.fetch("drift-001", "Unknown Corp", domain="unknown.com")
        assert snap is None

    async def test_domain_kwarg_preferred_over_name_heuristic(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(_SNAPSHOT_URL, _TIMESTAMP))
        adapter._fetch_text = AsyncMock(return_value="text")
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock):
            snap = await adapter.fetch("d", "Some Legal Name AG", domain="actual-domain.io")
        assert snap is not None
        assert snap.raw_data["domain"] == "actual-domain.io"

    async def test_derives_domain_from_name_when_absent(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(None, None))
        await adapter.fetch("d", "My Company")
        call_domain = adapter._find_snapshot.call_args[0][0]
        assert "my" in call_domain
        assert "company" in call_domain

    async def test_onboarding_date_forwarded_to_find_snapshot(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(None, None))
        await adapter.fetch("d", "Corp", domain=_DOMAIN, onboarding_date="20200101")
        adapter._find_snapshot.assert_awaited_once_with(_DOMAIN, "20200101")

    async def test_polite_delay_called_when_snapshot_found(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(_SNAPSHOT_URL, _TIMESTAMP))
        adapter._fetch_text = AsyncMock(return_value="text")
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await adapter.fetch("d", "Corp", domain=_DOMAIN)
        mock_sleep.assert_awaited_once_with(_POLITE_DELAY_S)

    async def test_no_delay_when_no_snapshot_found(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(None, None))
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await adapter.fetch("d", "Corp", domain=_DOMAIN)
        mock_sleep.assert_not_awaited()

    async def test_website_text_truncated_to_max_bytes(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(_SNAPSHOT_URL, _TIMESTAMP))
        # _fetch_text itself returns at most _MAX_TEXT_CHARS; simulate that.
        adapter._fetch_text = AsyncMock(return_value="X" * _MAX_TEXT_CHARS)
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock):
            snap = await adapter.fetch("d", "Corp", domain=_DOMAIN)
        assert snap is not None
        assert len(snap.raw_data["website_text"]) <= _MAX_TEXT_CHARS

    async def test_drift_id_propagated_to_snapshot(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(_SNAPSHOT_URL, _TIMESTAMP))
        adapter._fetch_text = AsyncMock(return_value="text")
        with patch("app.sources.wayback.asyncio.sleep", new_callable=AsyncMock):
            snap = await adapter.fetch("my-drift-42", "Corp", domain=_DOMAIN)
        assert snap is not None
        assert snap.drift_id == "my-drift-42"

    async def test_none_onboarding_date_forwarded_as_none(self):
        adapter = WaybackAdapter()
        adapter._find_snapshot = AsyncMock(return_value=(None, None))
        await adapter.fetch("d", "Corp", domain=_DOMAIN)
        adapter._find_snapshot.assert_awaited_once_with(_DOMAIN, None)


# ---------------------------------------------------------------------------
# WaybackAdapter.fetch_signals() — reference-only adapter
# ---------------------------------------------------------------------------

class TestWaybackFetchSignals:
    async def test_returns_empty_list_always(self):
        adapter = WaybackAdapter()
        result = await adapter.fetch_signals("drift-001", "Corp")
        assert result == []

    async def test_returns_empty_list_with_kwargs(self):
        adapter = WaybackAdapter()
        result = await adapter.fetch_signals(
            "drift-001", "Corp", since_month=6, domain=_DOMAIN
        )
        assert result == []

    async def test_no_network_calls_made(self):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        adapter = WaybackAdapter(http_client=mock_client)
        result = await adapter.fetch_signals("d", "Corp")
        assert result == []
        mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP helpers — _find_snapshot with representative cases
# ---------------------------------------------------------------------------

class TestFindSnapshot:
    async def test_returns_url_and_timestamp_on_found(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, _AVAILABILITY_FOUND)
        )
        url, ts = await adapter._find_snapshot(_DOMAIN, _TIMESTAMP)
        assert url == _SNAPSHOT_URL
        assert ts == _TIMESTAMP

    async def test_returns_none_when_not_available(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, _AVAILABILITY_NOT_FOUND)
        )
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_returns_none_when_available_false(self):
        payload = {
            "archived_snapshots": {
                "closest": {"available": False, "url": _SNAPSHOT_URL, "timestamp": _TIMESTAMP}
            }
        }
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, payload)
        )
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_returns_none_on_http_error(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(503)
        )
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_returns_none_on_transport_error(self):
        async def raise_transport(url, **kw):
            raise httpx.TransportError("connection reset")

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = raise_transport
        adapter = WaybackAdapter(http_client=mock_client)
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_returns_none_on_timeout(self):
        async def raise_timeout(url, **kw):
            raise httpx.ReadTimeout("timed out")

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = raise_timeout
        adapter = WaybackAdapter(http_client=mock_client)
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_returns_none_when_url_empty_string(self):
        payload = {
            "archived_snapshots": {
                "closest": {"available": True, "url": "", "timestamp": _TIMESTAMP}
            }
        }
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, payload)
        )
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_returns_none_on_invalid_json(self):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.is_success = True
        resp.json = MagicMock(side_effect=ValueError("bad json"))
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=resp)
        adapter = WaybackAdapter(http_client=mock_client)
        url, ts = await adapter._find_snapshot(_DOMAIN, None)
        assert url is None
        assert ts is None

    async def test_timestamp_included_in_request_params(self):
        calls: list[dict] = []

        async def capture(url, **kwargs):
            calls.append(kwargs.get("params", {}))
            return _mock_response(200, _AVAILABILITY_NOT_FOUND)

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = capture
        adapter = WaybackAdapter(http_client=mock_client)
        await adapter._find_snapshot(_DOMAIN, "20210101")
        assert calls[0].get("timestamp") == "20210101"

    async def test_timestamp_omitted_when_none(self):
        calls: list[dict] = []

        async def capture(url, **kwargs):
            calls.append(kwargs.get("params", {}))
            return _mock_response(200, _AVAILABILITY_NOT_FOUND)

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = capture
        adapter = WaybackAdapter(http_client=mock_client)
        await adapter._find_snapshot(_DOMAIN, None)
        assert "timestamp" not in calls[0]


# ---------------------------------------------------------------------------
# HTTP helpers — _fetch_text
# ---------------------------------------------------------------------------

class TestFetchText:
    async def test_extracts_text_from_html_response(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, text=_SAMPLE_HTML)
        )
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert _EXPECTED_TEXT_FRAGMENT in text

    async def test_returns_empty_on_http_error(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(404)
        )
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert text == ""

    async def test_returns_empty_on_503(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(503)
        )
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert text == ""

    async def test_returns_empty_on_transport_error(self):
        async def raise_transport(url, **kw):
            raise httpx.TransportError("timeout")

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = raise_transport
        adapter = WaybackAdapter(http_client=mock_client)
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert text == ""

    async def test_returns_empty_on_timeout(self):
        async def raise_timeout(url, **kw):
            raise httpx.ReadTimeout("timed out")

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = raise_timeout
        adapter = WaybackAdapter(http_client=mock_client)
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert text == ""

    async def test_ssrf_guard_rejects_non_archive_url(self):
        # The adapter must not fetch arbitrary URLs returned by the Wayback API.
        mock_client = MagicMock(spec=httpx.AsyncClient)
        adapter = WaybackAdapter(http_client=mock_client)
        text = await adapter._fetch_text("http://internal.corp/secret")
        assert text == ""
        mock_client.get.assert_not_called()

    async def test_ssrf_guard_allows_valid_wayback_url(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, text="<p>Hello</p>")
        )
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert "Hello" in text

    def test_allowed_snapshot_prefix_constant(self):
        assert _ALLOWED_SNAPSHOT_PREFIX == "https://web.archive.org/web/"

    async def test_truncates_text_to_max_bytes(self):
        long_html = "<p>" + ("A" * (_MAX_TEXT_CHARS + 2000)) + "</p>"
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, text=long_html)
        )
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert len(text) <= _MAX_TEXT_CHARS

    async def test_returns_empty_string_on_empty_body(self):
        adapter = _adapter_with_mock_get(
            lambda url, **kw: _mock_response(200, text="")
        )
        text = await adapter._fetch_text(_SNAPSHOT_URL)
        assert text == ""
