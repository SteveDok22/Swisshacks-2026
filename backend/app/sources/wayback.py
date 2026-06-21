"""
Wayback Machine — historical website snapshots (Internet Archive).

WHAT IT PROVIDES
    Point-in-time captures of a customer's public website. The Availability API
    returns the nearest snapshot URL to a given timestamp; the CDX API lists all
    captures for a URL (timestamp, status, digest). Together they recover the
    website *as it looked at KYC onboarding*.

WHY IT MATTERS HERE  (Use cases 9, 10)
    The "before" half of website-content drift. Pair the onboarding snapshot
    (Wayback) with the current page (Firecrawl) and the business-model comparator
    (sentence-transformer cosine distance) flags a silent pivot — e.g. a
    "boutique consultancy" that is now a crypto exchange. The CDX ``digest``
    column also gives a cheap "did the page change at all?".

COST / ACCESS  →  FREE, no API key
    Public best-effort service; no SLA, throttles under load — be polite.

    Availability: https://archive.org/wayback/available?url={url}&timestamp={ts}
    CDX:          https://web.archive.org/cdx/search/cdx?url={url}&output=json

SIGNAL FLOW
    This is a *reference-only* adapter. ``fetch()`` returns the onboarding-era
    website content as an ``EntitySnapshot``; signals are emitted by
    ``drift/business_model.py`` after cosine comparison with Firecrawl's current
    snapshot. ``fetch_signals()`` always returns ``[]``.

DOMAIN DISCOVERY
    ``fetch()`` accepts an explicit ``domain`` kwarg (e.g. "n26.com") from the
    service layer. When absent, a slug heuristic derives a candidate domain from
    the entity name (spaces → hyphens, lowercase, + ".com"). The heuristic
    frequently fails for non-.com entities; callers should prefer the stored
    ``EntitySnapshotDB.extra["domain"]`` value when it exists.

POLITENESS
    A 1 s delay separates the Availability API call from the content fetch so
    repeated single-entity scans stay well below the Internet Archive's informal
    rate limit. Callers that re-scan already-fetched domains should persist
    ``website_text`` in ``EntitySnapshotDB.extra`` and pass it to the
    business-model comparator directly, skipping a redundant re-fetch.
"""

from __future__ import annotations

import asyncio
import re
from html.parser import HTMLParser
from typing import Any

import httpx

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

_AVAILABILITY_URL = "https://archive.org/wayback/available"
_ALLOWED_SNAPSHOT_PREFIX = "https://web.archive.org/web/"
_USER_AGENT = "Sentinel/1.0 (hackathon research)"
_MAX_TEXT_CHARS = 10_000  # Unicode code points, not bytes
_POLITE_DELAY_S = 1.0

# Tags whose entire subtree content we discard — layout / chrome, not body text.
_SKIP_TAGS = frozenset({
    "script", "style", "noscript", "iframe",
    "head", "nav", "footer", "aside",
})


class _TextExtractor(HTMLParser):
    """Minimal, dependency-free HTML → plain-text extractor.

    Skips script / style / nav / footer blocks and collapses whitespace.
    Does not raise on malformed HTML — partial output is better than nothing.
    """

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:  # noqa: ARG002
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def text(self) -> str:
        joined = " ".join(self._parts)
        return re.sub(r"\s+", " ", joined).strip()


def _html_to_text(html: str) -> str:
    """Strip HTML tags and return collapsed plain text."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001
        # HTMLParser can raise on severely malformed input; return partial output.
        pass
    return parser.text()


def _name_to_domain(name: str) -> str:
    """Derive a naive .com domain from an entity name as a last-resort heuristic.

    Only used when the caller supplies no ``domain`` kwarg.  The result is
    frequently wrong for non-.com or non-English names; the service layer
    should always prefer the stored ``EntitySnapshotDB.extra["domain"]``.
    """
    slug = re.sub(r"[^a-z0-9-]", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"{slug}.com"


class WaybackAdapter(CostMixin, RegistryAdapter):
    """Internet Archive historical-snapshot connector.

    Provides the onboarding-era website content reference; the text comparison
    that turns this into a drift signal lives in ``drift/business_model.py``.

    Parameters
    ----------
    http_client:
        Optional injected ``httpx.AsyncClient`` for testing. When absent a
        private client is created per adapter instance and closed by ``aclose``.
    timeout:
        Per-request timeout in seconds (default 15 — Wayback can be slow).
    """

    source_name = "wayback"
    display_name = "Wayback Machine (Internet Archive)"
    base_url = "https://archive.org/wayback"
    docs_url = "https://archive.org/help/wayback_api.php"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (9, 10)
    signal_types = ("business_model_change", "domain_change")

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        if http_client is not None:
            self._http = http_client
            self._owns_client = False
        else:
            self._http = httpx.AsyncClient(
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
                timeout=timeout,
            )
            self._owns_client = True
        from app.core.api_cache import DiskCache
        self._cache = DiskCache("wayback")

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this adapter owns it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> "WaybackAdapter":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def record_url(self, entity_id: str) -> str | None:
        # entity_id is the domain / URL queried.
        return f"https://web.archive.org/web/*/{entity_id}"

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        """Fetch the website content as it appeared at KYC onboarding.

        Parameters
        ----------
        drift_id:
            Internal customer identifier.
        name:
            Entity legal name — used to derive a candidate domain when
            the ``domain`` kwarg is absent.
        domain:
            (kwarg) The entity's web domain, e.g. ``"example.com"``. Preferred
            over the name-slug heuristic and should come from
            ``EntitySnapshotDB.extra["domain"]`` when available.
        onboarding_date:
            (kwarg) Date string in ``yyyymmdd`` format, e.g. ``"20210315"``.
            Wayback returns the closest archived snapshot at or before this
            date. When absent, the most recent available snapshot is used.

        Returns
        -------
        EntitySnapshot with ``raw_data`` containing:
            ``domain``         — the domain that was queried
            ``snapshot_url``   — canonical Wayback URL of the capture
            ``snapshot_date``  — capture timestamp returned by the API
            ``website_text``   — extracted plain text (max 10 kB)
        Returns ``None`` when no snapshot is found or any network error occurs.
        """
        domain: str = kwargs.get("domain") or _name_to_domain(name)
        onboarding_date: str | None = kwargs.get("onboarding_date")

        # Cache the (often rate-limited) archive.org result on disk so the
        # historical snapshot is fetched once and then replays offline.
        cache_key = f"snapshot:{domain}:{onboarding_date or 'latest'}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return EntitySnapshot(
                drift_id=drift_id, name=name, source=self.source_name, raw_data=cached
            )

        snapshot_url, snapshot_date = await self._find_snapshot(domain, onboarding_date)
        if snapshot_url is None:
            return None

        # Polite delay between the Availability API call and the content fetch.
        await asyncio.sleep(_POLITE_DELAY_S)

        website_text = await self._fetch_text(snapshot_url)

        raw_data = {
            "domain": domain,
            "snapshot_url": snapshot_url,
            "snapshot_date": snapshot_date,
            "website_text": website_text,
        }
        if website_text:
            self._cache.set(cache_key, raw_data)
        return EntitySnapshot(
            drift_id=drift_id,
            name=name,
            source=self.source_name,
            raw_data=raw_data,
        )

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        """Always returns ``[]``.

        Wayback is a reference-only source. Signals are emitted by
        ``drift/business_model.py`` after cosine comparison with the current
        Firecrawl snapshot — not by this adapter.
        """
        return []

    # ------------------------------------------------------------------
    # HTTP helpers — both swallow all errors so a Wayback outage or a
    # domain with no archived snapshots never surfaces as an unhandled
    # exception in the drift service.
    # ------------------------------------------------------------------

    async def _find_snapshot(
        self, domain: str, timestamp: str | None
    ) -> tuple[str | None, str | None]:
        """Query the Availability API and return (snapshot_url, snapshot_date).

        Returns ``(None, None)`` when no snapshot exists, the domain has never
        been crawled, or the API call fails for any reason.
        """
        params: dict[str, str] = {"url": domain}
        if timestamp:
            params["timestamp"] = timestamp

        try:
            resp = await self._http.get(_AVAILABILITY_URL, params=params)
        except (httpx.TransportError, httpx.TimeoutException):
            return None, None
        if not resp.is_success:
            return None, None

        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            return None, None

        closest = data.get("archived_snapshots", {}).get("closest", {})
        if not closest or not closest.get("available"):
            return None, None

        url = closest.get("url")
        if not url:
            return None, None
        return url, closest.get("timestamp")

    async def _fetch_text(self, url: str) -> str:
        """Fetch a Wayback snapshot page and extract plain text.

        Guards against SSRF by rejecting any URL that does not start with the
        expected Wayback snapshot prefix — the Availability API should always
        return archive.org URLs, but we do not blindly trust external data.
        """
        if not url.startswith(_ALLOWED_SNAPSHOT_PREFIX):
            return ""
        try:
            resp = await self._http.get(url)
        except (httpx.TransportError, httpx.TimeoutException):
            return ""
        if not resp.is_success:
            return ""

        text = _html_to_text(resp.text)
        return text[:_MAX_TEXT_CHARS]
