"""
Firecrawl — website-to-markdown scraping.

WHAT IT PROVIDES
    Robust extraction of a live web page into clean markdown/structured content,
    handling JS rendering, proxies and anti-bot measures. ``/scrape`` returns one
    page; ``/crawl`` walks a site; ``/map`` lists URLs.

WHY IT MATTERS HERE  (Use cases 9, 10)
    The "after" half of website-content drift: it produces the CURRENT page text
    that the business-model comparator embeds and compares against the Wayback
    onboarding snapshot. A large cosine distance => ``business_model_change``.

COST / ACCESS  →  FREEMIUM, API key for cloud (IMPLEMENTED)
    Cloud free tier: ~1,000 credits/month (1 credit/page), no card required —
    enough for a hackathon. Self-hostable (AGPL-3.0) for free but operationally
    heavy (headless browsers, proxies). AGPL matters if you redistribute.

    Base URL:  https://api.firecrawl.dev/v1/
    Endpoints: POST /scrape  (-> markdown)   POST /crawl   POST /map
    Auth:      ``Authorization: Bearer {FIRECRAWL_API_KEY}``

GRACEFUL DEGRADATION
    The Firecrawl key is OPTIONAL. ``fetch`` resolves a current-website snapshot
    along a three-tier ladder, each tier a fallback for the one above:

      1. Firecrawl cloud ``/scrape`` (clean markdown, JS-rendered) — key present.
      2. Plain ``httpx.GET`` of ``https://{domain}`` + a stdlib HTML-to-text
         strip — zero-cost, no key, no extra dependency.
      3. An empty-``website_text`` snapshot — the page was unreachable, but the
         engine still gets a (degraded) snapshot. The business-model comparator
         skips the cosine compare whenever either side's text is empty.

    ``fetch`` only returns ``None`` when it has no ``domain`` to scrape at all.

DEPENDENCY RULE
    This adapter does NOT touch the database. The caller (the future aggregator)
    injects the customer's ``domain`` — read from ``EntitySnapshotDB.extra`` —
    as a keyword argument, exactly as ``ZefixAdapter`` takes an injected
    ``baseline``. Keeping the DB lookup out of the adapter preserves the
    ``sources`` dependency rule and makes the adapter unit-testable without an ORM.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

logger = get_logger(__name__)

_USER_AGENT = "Sentinel/1.0 (+https://github.com/swisshacks-2026)"

# Hard cap on stored website text — the comparator embeds it, and the onboarding
# baseline (Wayback) is trimmed to the same 10 kB, so keep them symmetric.
_MAX_TEXT = 10_000

# HTML tags whose *content* is never page copy — dropped wholesale in the
# zero-cost fallback so script/style payloads don't pollute the embedding.
_NON_CONTENT_TAGS = frozenset({"script", "style", "noscript", "template", "head"})

# Collapse any run of whitespace (incl. newlines) to a single space.
_WS = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    """Minimal stdlib HTML-to-text strip — the no-dependency BeautifulSoup stand-in.

    Collects text data outside of non-content tags. Good enough to recover the
    visible copy for an embedding comparison; it is NOT a full renderer (that is
    what the Firecrawl cloud tier is for).

    Skip state is a *stack of tag names*, not a counter: ``html.parser`` parses
    tag soup permissively, so a mismatched close tag (e.g. ``</template>`` while
    inside ``<noscript>``) fires a real ``handle_endtag``. A counter would
    decrement on that stray close and prematurely re-enable text capture; a stack
    only pops when the top tag actually matches, so nested/unbalanced markup keeps
    the enclosing non-content body suppressed.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _NON_CONTENT_TAGS:
            self._skip_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip_stack:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        return _WS.sub(" ", " ".join(self._chunks)).strip()


def _html_to_text(html: str) -> str:
    """Strip an HTML document to a single whitespace-normalised text line."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed markup must degrade, not raise
        # A pathological document should yield whatever was parsed so far rather
        # than break the scan; the comparator tolerates a short/empty string.
        logger.warning("firecrawl_html_parse_failed")
    return parser.get_text()


def _normalise_domain(domain: str) -> str:
    """Reduce a raw domain/URL to a bare host (no scheme, path, query or fragment)."""
    host = domain.strip()
    host = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", host)  # drop scheme
    host = host.split("/", 1)[0]   # drop any path
    host = host.split("?", 1)[0]   # drop query string (path-less URLs)
    host = host.split("#", 1)[0]   # drop fragment
    return host.strip().rstrip(".").lower()


def _is_blocked_host(host: str) -> bool:
    """True when ``host`` is a literal private / loopback / link-local IP.

    A lightweight SSRF guard: the ``domain`` is injected from the (trusted) KYC
    baseline, so the risk is low, but blocking literal internal IPs is cheap and
    stops the trivial ``localhost`` / RFC-1918 cases without a DNS round-trip.
    The well-known ``localhost`` name is special-cased; other hostnames are
    intentionally *not* resolved here (no DNS-rebinding defence — that belongs at
    the egress layer, not in an adapter).
    """
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # a hostname, not a literal IP → allowed
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


class FirecrawlAdapter(CostMixin, RegistryAdapter):
    """Live website-content scraper.

    Supplies page text rather than canonical registry fields; the real diff is
    embedding-distance in the business-model comparator (``drift/business_model``),
    so ``fetch_signals`` is intentionally a no-op here.
    """

    source_name = "firecrawl"
    display_name = "Firecrawl (website scrape)"
    base_url = "https://api.firecrawl.dev/v1"
    docs_url = "https://docs.firecrawl.dev/"
    cost = SourceCost.FREEMIUM
    # PLANNED is the registry's "usable / not skipped" state (the invariant is
    # PLANNED⟺FREE/FREEMIUM, enforced by tests). This adapter is FULLY
    # IMPLEMENTED: with a key it scrapes the cloud tier, without one it falls
    # back to a plain-HTTP strip, and it never calls ``_carcass()``.
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (9, 10)
    signal_types = ("business_model_change",)

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        # Fall back to configured key when not explicitly injected.
        self._api_key = settings.firecrawl_api_key if api_key is None else api_key
        # An injected client (tests / shared pool) is reused and never closed by
        # this adapter; otherwise a short-lived client is created per fetch().
        self._client = client
        self._timeout = timeout

    @property
    def _has_key(self) -> bool:
        return bool(self._api_key)

    # ------------------------------------------------------------------ #
    # Public contract                                                      #
    # ------------------------------------------------------------------ #
    async def fetch(
        self,
        drift_id: str,
        name: str,
        *,
        domain: str | None = None,
        **kwargs: Any,
    ) -> EntitySnapshot | None:
        """Fetch the CURRENT website content for ``domain`` as plain text.

        ``domain`` is the customer's website host, injected by the caller from
        ``EntitySnapshotDB.extra["domain"]`` (the adapter never reads the DB).
        Returns ``None`` only when no domain is available — otherwise it always
        returns a snapshot, falling back through cloud → plain-HTTP → empty so a
        single unreachable (or internal) page never aborts the scan.

        A single ``httpx`` client is created once per call (when none is injected)
        and shared across both scrape tiers, so the degraded path does not pay for
        two SSL handshakes.
        """
        host = _normalise_domain(domain) if domain else ""
        if not host:
            logger.info("firecrawl_no_domain", drift_id=drift_id, name=name)
            return None

        url = f"https://{host}"
        text = ""
        method = "empty"

        if _is_blocked_host(host):
            # Refuse to scrape internal addresses; degrade to an empty snapshot.
            logger.warning("firecrawl_blocked_host", drift_id=drift_id, host=host)
            method = "blocked"
        else:
            client = self._client or self._new_client()
            owns_client = self._client is None
            try:
                if self._has_key:
                    text = await self._scrape_cloud(client, url, drift_id)
                    method = "firecrawl" if text else "empty"
                if not text:
                    # Either no key, or the cloud scrape failed → zero-cost fallback.
                    fallback = await self._scrape_plain(client, url, drift_id)
                    if fallback:
                        text, method = fallback, "plain_http"
            finally:
                if owns_client:
                    await client.aclose()

        return EntitySnapshot(
            drift_id=drift_id,
            name=name,
            source=self.source_name,
            raw_data={
                "domain": host,
                "url": url,
                "website_text": text[:_MAX_TEXT],
                "scraped_at": datetime.now(UTC).isoformat(),
                "scrape_method": method,
            },
        )

    async def fetch_signals(
        self,
        drift_id: str,
        name: str,
        since_month: int = 0,
        **kwargs: Any,
    ) -> list[PublicSignal]:
        """Firecrawl emits no signals directly.

        Business-model drift is detected by ``drift/business_model.py``, which
        embeds this adapter's ``website_text`` against the Wayback onboarding
        snapshot and emits ``business_model_change`` on a large cosine distance.
        """
        return []

    # ------------------------------------------------------------------ #
    # Scrape tiers                                                          #
    # ------------------------------------------------------------------ #
    async def _scrape_cloud(self, client: httpx.AsyncClient, url: str, drift_id: str) -> str:
        """Tier 1 — Firecrawl cloud ``/scrape`` → clean markdown.

        Returns the markdown (possibly empty) on success, or ``""`` on any HTTP
        / network / shape error so ``fetch`` can fall through to the plain-HTTP
        tier. The RegistryAdapter "errors propagate" rule is relaxed here on
        purpose: a scrape failure must degrade to the fallback, not abort the
        whole customer scan.
        """
        try:
            resp = await client.post(
                f"{self.base_url}/scrape",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": _USER_AGENT,
                },
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            # v1 shape: {"success": true, "data": {"markdown": "...", ...}}
            data = payload.get("data") if isinstance(payload, dict) else None
            markdown = data.get("markdown") if isinstance(data, dict) else None
            return markdown.strip() if isinstance(markdown, str) else ""
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("firecrawl_cloud_failed", drift_id=drift_id, url=url, error=str(exc))
            return ""
        except ValueError as exc:
            # JSONDecodeError (a ValueError) — malformed body; degrade to fallback.
            logger.warning("firecrawl_cloud_bad_payload", drift_id=drift_id, url=url, error=str(exc))
            return ""

    async def _scrape_plain(self, client: httpx.AsyncClient, url: str, drift_id: str) -> str:
        """Tier 2 — plain ``httpx.GET`` + stdlib HTML-to-text strip (no key, no cost)."""
        try:
            resp = await client.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
            resp.raise_for_status()
            return _html_to_text(resp.text)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("firecrawl_plain_failed", drift_id=drift_id, url=url, error=str(exc))
            return ""

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout)
