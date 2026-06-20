"""
Tests for the Firecrawl adapter (``app.sources.firecrawl``).

The HTTP layer is mocked with ``httpx.MockTransport`` so these run fully offline
— no Firecrawl key and no network are required. The adapter's defining property
is its three-tier fallback ladder (cloud ``/scrape`` → plain ``GET`` + HTML strip
→ empty snapshot), so the bulk of these tests pin which tier serves a given
configuration and that a failure in one tier degrades to the next rather than
raising.
"""

from __future__ import annotations

import httpx
import pytest

from app.sources.base import EntitySnapshot
from app.sources.firecrawl import (
    _MAX_TEXT,
    FirecrawlAdapter,
    _html_to_text,
    _normalise_domain,
)

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
_MARKDOWN = "# Helvetia Trading AG\n\nBoutique import/export consultancy in Zug."

_CLOUD_OK = {"success": True, "data": {"markdown": _MARKDOWN, "metadata": {"statusCode": 200}}}

_HTML_PAGE = """
<html>
  <head><title>ignored</title><style>.x{color:red}</style></head>
  <body>
    <script>var tracker = 1;</script>
    <h1>Helvetia Trading AG</h1>
    <p>Boutique import/export consultancy in Zug.</p>
  </body>
</html>
"""


def _make_adapter(handler, *, api_key: str | None = None) -> FirecrawlAdapter:
    """Build a FirecrawlAdapter wired to a MockTransport handler."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FirecrawlAdapter(api_key=api_key, client=client)


def _cloud_handler(request: httpx.Request) -> httpx.Response:
    """POST /scrape → cloud markdown; anything else → 404."""
    if request.url.path.endswith("/scrape") and request.method == "POST":
        return httpx.Response(200, json=_CLOUD_OK)
    return httpx.Response(404)


# --------------------------------------------------------------------------- #
# Pure helpers                                                                 #
# --------------------------------------------------------------------------- #
class TestHelpers:
    def test_normalise_domain_strips_scheme_path_and_case(self):
        assert _normalise_domain("https://Helvetia.example.com/about?x=1") == "helvetia.example.com"
        assert _normalise_domain("helvetia.example.com") == "helvetia.example.com"
        assert _normalise_domain("http://helvetia.example.com/") == "helvetia.example.com"
        assert _normalise_domain("  helvetia.example.com.  ") == "helvetia.example.com"

    def test_normalise_domain_strips_pathless_query_and_fragment(self):
        # A query/fragment with no explicit path must not survive into the host.
        assert _normalise_domain("helvetia.example.com?foo=bar") == "helvetia.example.com"
        assert _normalise_domain("helvetia.example.com#anchor") == "helvetia.example.com"

    def test_html_to_text_drops_script_and_style(self):
        text = _html_to_text(_HTML_PAGE)
        assert "Helvetia Trading AG" in text
        assert "Boutique import/export consultancy" in text
        # Non-content tags must not leak into the embedding text.
        assert "tracker" not in text
        assert "color:red" not in text
        assert "ignored" not in text  # <title> lives in <head>

    def test_html_to_text_suppresses_body_through_mismatched_close_tag(self):
        # Tag-soup: a stray </template> inside <noscript> must NOT re-enable
        # capture — the stack only pops on a matching close tag (counter bug).
        html = "<p>visible</p><noscript>hidden<!--x--></template>still hidden</noscript><p>after</p>"
        text = _html_to_text(html)
        assert "visible" in text
        assert "after" in text
        assert "hidden" not in text
        assert "still hidden" not in text

    def test_html_to_text_collapses_whitespace(self):
        assert _html_to_text("<p>a\n\n   b\t c</p>") == "a b c"

    def test_html_to_text_tolerates_malformed_markup(self):
        # A broken document must degrade to whatever parsed, never raise.
        assert "hello" in _html_to_text("<p>hello <b>world").lower()


# --------------------------------------------------------------------------- #
# fetch() — tier selection and degradation                                    #
# --------------------------------------------------------------------------- #
class TestFetchCloudTier:
    async def test_cloud_scrape_returns_markdown(self):
        snap = await _make_adapter(_cloud_handler, api_key="fc-key").fetch(
            "drift-001", "Helvetia Trading AG", domain="helvetia.example.com"
        )
        assert isinstance(snap, EntitySnapshot)
        assert snap.source == "firecrawl"
        assert snap.drift_id == "drift-001"
        assert snap.raw_data["website_text"] == _MARKDOWN
        assert snap.raw_data["scrape_method"] == "firecrawl"
        assert snap.raw_data["domain"] == "helvetia.example.com"
        assert snap.raw_data["url"] == "https://helvetia.example.com"
        assert "scraped_at" in snap.raw_data

    async def test_cloud_failure_falls_back_to_plain_http(self):
        # POST /scrape 500s, GET serves HTML → adapter must degrade, not raise.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/scrape"):
                return httpx.Response(500)
            return httpx.Response(200, text=_HTML_PAGE)

        snap = await _make_adapter(handler, api_key="fc-key").fetch(
            "d", "Helvetia", domain="helvetia.example.com"
        )
        assert snap.raw_data["scrape_method"] == "plain_http"
        assert "Boutique import/export consultancy" in snap.raw_data["website_text"]

    async def test_cloud_bad_payload_falls_back_to_plain_http(self):
        # 200 but no data.markdown → treated as a failed scrape, falls through.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/scrape"):
                return httpx.Response(200, json={"success": False, "error": "blocked"})
            return httpx.Response(200, text=_HTML_PAGE)

        snap = await _make_adapter(handler, api_key="fc-key").fetch(
            "d", "Helvetia", domain="helvetia.example.com"
        )
        assert snap.raw_data["scrape_method"] == "plain_http"

    async def test_whitespace_only_markdown_falls_back_to_plain_http(self):
        # data.markdown present but blank → stripped to "" → treated as a miss.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/scrape"):
                return httpx.Response(200, json={"success": True, "data": {"markdown": "   \n\t "}})
            return httpx.Response(200, text=_HTML_PAGE)

        snap = await _make_adapter(handler, api_key="fc-key").fetch(
            "d", "Helvetia", domain="helvetia.example.com"
        )
        assert snap.raw_data["scrape_method"] == "plain_http"


class TestFetchPlainTier:
    async def test_no_key_uses_plain_http_directly(self):
        # No key → cloud tier is skipped entirely; GET is the only request.
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET", "cloud scrape must not run without a key"
            return httpx.Response(200, text=_HTML_PAGE)

        snap = await _make_adapter(handler, api_key="").fetch(
            "d", "Helvetia", domain="helvetia.example.com"
        )
        assert snap.raw_data["scrape_method"] == "plain_http"
        assert "Helvetia Trading AG" in snap.raw_data["website_text"]


class TestFetchEmptyTier:
    async def test_all_tiers_fail_returns_empty_snapshot_not_none(self):
        # No key and the site is unreachable → still a snapshot, just empty text.
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("unreachable")

        snap = await _make_adapter(handler, api_key="").fetch(
            "d", "Helvetia", domain="dead.example.com"
        )
        assert snap is not None
        assert snap.raw_data["website_text"] == ""
        assert snap.raw_data["scrape_method"] == "empty"

    async def test_no_domain_returns_none(self):
        def explode(request):  # pragma: no cover - must never be called
            raise AssertionError("HTTP must not be attempted without a domain")

        adapter = _make_adapter(explode, api_key="fc-key")
        assert await adapter.fetch("d", "Helvetia", domain=None) is None
        assert await adapter.fetch("d", "Helvetia", domain="   ") is None


class TestFetchSsrfGuard:
    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "192.168.1.1", "10.0.0.5", "169.254.1.1"])
    async def test_internal_hosts_are_not_scraped(self, host):
        # A literal private/loopback/link-local host must never trigger HTTP;
        # it degrades to an empty 'blocked' snapshot, not None.
        def explode(request):  # pragma: no cover - must never be called
            raise AssertionError(f"internal host {host!r} must not be scraped")

        snap = await _make_adapter(explode, api_key="fc-key").fetch(
            "d", "Internal", domain=host
        )
        assert snap is not None
        assert snap.raw_data["scrape_method"] == "blocked"
        assert snap.raw_data["website_text"] == ""

    async def test_public_host_is_still_scraped(self):
        snap = await _make_adapter(_cloud_handler, api_key="fc-key").fetch(
            "d", "Helvetia", domain="93.184.216.34"  # public literal IP
        )
        assert snap.raw_data["scrape_method"] == "firecrawl"


class TestFetchMisc:
    async def test_website_text_is_truncated(self):
        big = "x" * (_MAX_TEXT + 5_000)
        payload = {"success": True, "data": {"markdown": big}}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        snap = await _make_adapter(handler, api_key="fc-key").fetch(
            "d", "Big Corp", domain="big.example.com"
        )
        assert len(snap.raw_data["website_text"]) == _MAX_TEXT

    async def test_domain_with_scheme_and_path_is_normalised(self):
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            return httpx.Response(200, json=_CLOUD_OK)

        snap = await _make_adapter(handler, api_key="fc-key").fetch(
            "d", "Helvetia", domain="https://helvetia.example.com/about"
        )
        # The injected raw URL/path is reduced to a bare host before scraping.
        assert snap.raw_data["domain"] == "helvetia.example.com"
        assert snap.raw_data["url"] == "https://helvetia.example.com"


# --------------------------------------------------------------------------- #
# fetch_signals() — Firecrawl is signal-silent by design                      #
# --------------------------------------------------------------------------- #
class TestFetchSignals:
    async def test_returns_empty_list(self):
        # Signals come from the business-model comparator, not this adapter.
        adapter = FirecrawlAdapter(api_key="fc-key")
        assert await adapter.fetch_signals("d", "Helvetia") == []
        assert await adapter.fetch_signals("d", "Helvetia", since_month=6) == []


# --------------------------------------------------------------------------- #
# Construction / config                                                       #
# --------------------------------------------------------------------------- #
class TestConstruction:
    def test_no_arg_construction_uses_configured_key(self):
        # Must be instantiable with no args (registry/catalogue use the class).
        adapter = FirecrawlAdapter()
        assert adapter.source_name == "firecrawl"
        # record_url stays None — Firecrawl scrapes arbitrary URLs, no record link.
        assert adapter.record_url("x") is None

    def test_injected_key_overrides_config(self):
        assert FirecrawlAdapter(api_key="explicit")._has_key is True
        assert FirecrawlAdapter(api_key="")._has_key is False
