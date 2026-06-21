"""
Event Registry / NewsAPI.ai — structured news event aggregation.

WHAT IT PROVIDES
    News clustered into de-duplicated *events* (20-50 articles → one Event),
    which makes spike detection robust against syndication/SEO noise.
    Entity-aware queries return events *about* a named company rather than
    simple keyword matches. Each result carries a relevance score, event
    sentiment, and article-level source quality rating.

WHY WE IMPLEMENT IT  →  hackathon API key provided; GDELT is the free fallback
    Previously skipped as trial-only. SwissHacks 2026 hackathon provides an
    API key with full access. ``fetch`` / ``fetch_signals`` are fully
    implemented. Event Registry is the PRIMARY news source for Cases 1, 6, 8,
    10; GdeltAdapter remains as the always-on free fallback when the key is
    absent.

    Base URL:   https://eventregistry.org/api/v1/  (a.k.a. newsapi.ai)
    Auth:       ``"apiKey": key`` in POST body.
    Key env:    ``EVENT_REGISTRY_API_KEY``
    Rate limit: 2,500 requests / day on hackathon tier; no per-second limit.

    Key endpoints (all POST, JSON body):
        /event/getEvents       — clustered events about entity (UC 1)
        /article/getArticles   — articles about entity (UC 6, 8, 10)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings
from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

logger = logging.getLogger(__name__)

_BASE_URL = "https://eventregistry.org/api/v1"
_USER_AGENT = "Sentinel/1.0 (hackathon; SwissHacks 2026)"

_FUNDING_KEYWORDS = ["funding", "investment", "raised", "capital raise", "IPO"]
_NAME_CHANGE_KEYWORDS = ["name change", "renamed", "rebranded", "formerly known", "changes its name"]
_PIVOT_KEYWORDS = ["pivot", "rebranding", "new product", "business model change", "strategic shift"]


def _sentiment_to_severity(sentiment: float | None) -> float:
    """Map EventRegistry sentiment (−1..+1) to PublicSignal severity (0..1)."""
    if sentiment is None:
        return 0.40
    if sentiment < -0.5:
        return 0.85
    if sentiment < -0.2:
        return 0.65
    if sentiment < 0.0:
        return 0.45
    return 0.25


_LEGAL_TOKENS = frozenset(
    {
        "s.a.", "sa", "ag", "gmbh", "ltd", "ltd.", "inc", "inc.", "plc", "llc",
        "a/s", "co", "co.", "corp", "corp.", "sarl", "bv", "nv", "spa", "oyj",
        "ab", "as", "pte", "limited", "trading",
    }
)


def _name_query_variants(name: str) -> list[str]:
    """Query variants from most- to least-specific.

    The full legal name first, then the name with legal-form tokens stripped,
    then the leading distinctive token. Lets a real entity yield real article
    coverage even when the exact legal name (e.g. "Rosneft Trading S.A.") has
    little direct press but the brand ("Rosneft") has plenty.
    """
    variants = [name]
    tokens = name.replace(",", " ").split()
    core = [t for t in tokens if t.strip(".").lower() not in _LEGAL_TOKENS]
    seen = {name.lower()}
    if core and len(core) < len(tokens):
        cand = " ".join(core)
        if cand.lower() not in seen:
            variants.append(cand)
            seen.add(cand.lower())
    if len(core) > 1:
        lead = core[0]
        if lead.lower() not in seen:
            variants.append(lead)
    return variants


def _month_offset_to_date(since_month: int) -> str:
    """Convert a zero-indexed month offset to an ISO date string for ``dateStart``.

    since_month=0  → 12 months ago (full history window)
    since_month=6  → 6 months ago
    since_month=11 → 1 month ago
    """
    delta_months = max(1, 12 - since_month)
    date = datetime.now(UTC) - timedelta(days=delta_months * 30)
    return date.strftime("%Y-%m-%d")


def _date_str_to_month(date_str: str, since_month: int) -> int:
    """Estimate the signal month index from an ISO date string.

    Maps backward from today: today → month 11, ~30 days ago → month 10, …
    Result is clamped to [since_month, 11].
    """
    try:
        dt = datetime.fromisoformat(date_str[:10])
        delta_days = (datetime.now(UTC).date() - dt.date()).days
        month_index = max(0, 11 - delta_days // 30)
    except (ValueError, TypeError):
        month_index = since_month
    return max(since_month, min(11, month_index))


class EventRegistryAdapter(CostMixin, RegistryAdapter):
    """Structured news-event aggregation — primary news source (hackathon key)."""

    source_name = "event_registry"
    display_name = "Event Registry / NewsAPI.ai"
    base_url = _BASE_URL
    docs_url = "https://newsapi.ai/documentation"
    cost = SourceCost.FREEMIUM
    # PLANNED is the correct value here — the registry invariant is
    # PLANNED↔FREE/FREEMIUM (enforced by tests). This adapter is FULLY
    # IMPLEMENTED: fetch returns None, fetch_signals runs live API calls
    # when the key is set, and returns [] when absent. PLANNED means
    # "usable / not skipped", not "carcass" — AdapterStatus has no LIVE
    # variant; the distinction lives in whether _carcass() is called (it
    # isn't here).
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (1, 6, 8, 10)
    signal_types = (
        "news",
        "adverse_media",
        "funding_event",
        "name_change",
        "business_model_change",
    )

    def __init__(self) -> None:
        self._api_key: str = settings.event_registry_api_key
        from app.core.api_cache import DiskCache
        self._cache = DiskCache("event_registry")

    @property
    def _is_configured(self) -> bool:
        return bool(self._api_key)

    def record_url(self, entity_id: str) -> str | None:
        if not entity_id:
            return None
        return f"https://eventregistry.org/event/{entity_id}"

    # ------------------------------------------------------------------
    # Public contract
    # ------------------------------------------------------------------

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        """Event Registry is a news source only — no canonical entity record."""
        return None

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        """Fetch public news signals for *name* from the Event Registry API.

        Returns ``[]`` (not an error) when no key is configured — GDELT is the
        always-on fallback. Three detection modes run concurrently:

        - adverse-media / news-spike scan (UC 1): event search with sentiment
        - funding events (UC 6): article search with funding keywords
        - name-change / pivot scan (UC 8, 10): article search with rebrand keywords
        """
        if not self._is_configured:
            logger.debug("EVENT_REGISTRY_API_KEY not set — Event Registry skipped")
            return []

        since_month = max(0, min(11, since_month))
        date_from = _month_offset_to_date(since_month)
        date_to = datetime.now(UTC).strftime("%Y-%m-%d")

        try:
            adverse, funding, pivot = await asyncio.gather(
                self._fetch_adverse_media(name, date_from, date_to, since_month),
                self._fetch_funding_events(name, date_from, date_to, since_month),
                self._fetch_name_pivot_articles(name, date_from, date_to, since_month),
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Event Registry HTTP %d for %r", exc.response.status_code, name
            )
            return []
        except httpx.RequestError as exc:
            logger.warning("Event Registry network error for %r: %s", name, exc)
            return []

        return adverse + funding + pivot

    # ------------------------------------------------------------------
    # Private helpers — one per detection mode
    # ------------------------------------------------------------------

    async def _post(
        self, endpoint: str, payload: dict[str, Any], *, retries: int = 3
    ) -> dict[str, Any]:
        """POST to Event Registry with exponential backoff on 429."""
        if retries < 1:
            raise ValueError(f"retries must be >= 1, got {retries}")

        import hashlib as _hl
        cache_key = f"{endpoint}:{_hl.sha256(str(sorted(payload.items())).encode()).hexdigest()[:16]}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = {**payload, "apiKey": self._api_key}
        url = f"{_BASE_URL}/{endpoint}"
        headers = {"User-Agent": _USER_AGENT, "Content-Type": "application/json"}

        last_response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(retries):
                resp = await client.post(url, json=payload, headers=headers)
                last_response = resp
                if resp.status_code == 429:
                    if attempt < retries - 1:
                        wait = 2**attempt
                        logger.debug(
                            "Event Registry 429 — retrying in %ds (attempt %d/%d)",
                            wait,
                            attempt + 1,
                            retries,
                        )
                        await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                self._cache.set(cache_key, data)
                return data

        # All retries exhausted on 429.
        raise httpx.HTTPStatusError(
            f"Event Registry returned 429 after {retries} retries",
            request=last_response.request,  # type: ignore[union-attr]
            response=last_response,  # type: ignore[arg-type]
        )

    async def _fetch_adverse_media(
        self, name: str, date_from: str, date_to: str, since_month: int
    ) -> list[PublicSignal]:
        """UC 1 — adverse-media / negative-news-spike via event-level search."""
        payload: dict[str, Any] = {
            "action": "getEvents",
            "keyword": name,
            "dateStart": date_from,
            "dateEnd": date_to,
            "lang": "eng",
            "resultType": "events",
            "eventsCount": 20,
            "eventsSortBy": "date",
            "returnInfo": {
                "eventInfo": {"sentiment": True, "articleCounts": True}
            },
        }
        data = await self._post("event/getEvents", payload)
        events = (data.get("events") or {}).get("results", [])

        signals: list[PublicSignal] = []
        for ev in events:
            sentiment: float | None = ev.get("sentiment")
            if sentiment is None or sentiment >= 0.0:
                continue  # neutral and positive events do not qualify
            title = ev.get("title", {})
            headline = (title.get("eng") if isinstance(title, dict) else title) or name
            article_count: int = ev.get("articleCounts", {}).get("eng", 1)
            severity = _sentiment_to_severity(sentiment)
            month = _date_str_to_month(ev.get("eventDate", date_from), since_month)
            signals.append(
                PublicSignal(
                    month=month,
                    signal_type="adverse_media" if severity >= 0.65 else "news",
                    headline=str(headline)[:200],
                    severity=severity,
                    source=self.display_name,
                    source_url=self.record_url(ev.get("uri", "")),
                )
            )
            # High-volume cluster → additional volume-spike signal.
            if article_count >= 10:
                signals.append(
                    PublicSignal(
                        month=month,
                        signal_type="news",
                        headline=f"News spike: {article_count} articles — {str(headline)[:80]}",
                        severity=min(0.95, severity + 0.10),
                        source=self.display_name,
                        source_url=self.record_url(ev.get("uri", "")),
                    )
                )
        return signals

    async def _fetch_funding_events(
        self, name: str, date_from: str, date_to: str, since_month: int
    ) -> list[PublicSignal]:
        """UC 6 — funding / expansion news via article search."""
        quoted_keywords = " OR ".join(f'"{k}"' for k in _FUNDING_KEYWORDS)
        keyword_query = f"{name} ({quoted_keywords})"
        payload: dict[str, Any] = {
            "action": "getArticles",
            "keyword": keyword_query,
            "dateStart": date_from,
            "dateEnd": date_to,
            "lang": "eng",
            "resultType": "articles",
            "articlesCount": 10,
            "articlesSortBy": "date",
            "returnInfo": {"articleInfo": {"bodyLen": 0, "sentiment": False}},
        }
        data = await self._post("article/getArticles", payload)
        articles = (data.get("articles") or {}).get("results", [])

        signals: list[PublicSignal] = []
        for art in articles:
            headline = art.get("title") or f"Funding event — {name}"
            month = _date_str_to_month(
                str(art.get("dateTime", date_from))[:10], since_month
            )
            source_name = (art.get("source") or {}).get("title") or self.display_name
            signals.append(
                PublicSignal(
                    month=month,
                    signal_type="funding_event",
                    headline=str(headline)[:200],
                    severity=0.55,
                    source=source_name,
                    source_url=art.get("url"),
                )
            )
        return signals

    async def fetch_recent_news(
        self, drift_id: str, name: str, since_month: int = 0, max_articles: int = 8
    ) -> list[PublicSignal]:
        """Best-effort REAL recent articles about *name* as news signals.

        Unlike ``fetch_signals`` (which gates the adverse-media scan on negative
        event sentiment), this returns the latest real articles with their REAL
        title and REAL ``source_url`` — so a live entity's signal cards link
        straight to the actual article instead of a search page, even when the
        sentiment-gated scan finds nothing. Returns ``[]`` without a key or on
        any error. Cached via ``_post``.
        """
        if not self._is_configured:
            return []
        since_month = max(0, min(11, since_month))
        date_from = _month_offset_to_date(since_month)
        date_to = datetime.now(UTC).strftime("%Y-%m-%d")

        # Try the full legal name first; if it has no coverage, retry with the
        # simplified core name (e.g. "Rosneft Trading S.A." -> "Rosneft") so a
        # real entity reliably yields real article links instead of nothing.
        articles: list[dict[str, Any]] = []
        for query in _name_query_variants(name):
            payload: dict[str, Any] = {
                "action": "getArticles",
                "keyword": query,
                "dateStart": date_from,
                "dateEnd": date_to,
                "lang": "eng",
                "resultType": "articles",
                "articlesCount": max_articles,
                "articlesSortBy": "date",
                "returnInfo": {"articleInfo": {"sentiment": True, "bodyLen": 0}},
            }
            try:
                data = await self._post("article/getArticles", payload)
            except (httpx.HTTPStatusError, httpx.RequestError):
                return []
            articles = (data.get("articles") or {}).get("results", [])
            if articles:
                break
        signals: list[PublicSignal] = []
        for art in articles:
            url = art.get("url")
            title = art.get("title")
            if not url or not title:
                continue
            sentiment = art.get("sentiment")
            severity = _sentiment_to_severity(sentiment)
            stype = (
                "adverse_media"
                if (sentiment is not None and sentiment < -0.2)
                else "news"
            )
            month = _date_str_to_month(
                str(art.get("dateTime", date_from))[:10], since_month
            )
            source_name = (art.get("source") or {}).get("title") or self.display_name
            signals.append(
                PublicSignal(
                    month=month,
                    signal_type=stype,
                    headline=str(title)[:200],
                    severity=severity,
                    source=source_name,
                    source_url=url,
                )
            )
        return signals

    async def _fetch_name_pivot_articles(
        self, name: str, date_from: str, date_to: str, since_month: int
    ) -> list[PublicSignal]:
        """UC 8 / 10 — name-change / business-model-pivot via article search."""
        all_kw = _NAME_CHANGE_KEYWORDS + _PIVOT_KEYWORDS
        quoted_keywords = " OR ".join(f'"{k}"' for k in all_kw)
        keyword_query = f"{name} ({quoted_keywords})"
        payload: dict[str, Any] = {
            "action": "getArticles",
            "keyword": keyword_query,
            "dateStart": date_from,
            "dateEnd": date_to,
            "lang": "eng",
            "resultType": "articles",
            "articlesCount": 10,
            "articlesSortBy": "date",
            "returnInfo": {"articleInfo": {"bodyLen": 0, "sentiment": False}},
        }
        data = await self._post("article/getArticles", payload)
        articles = (data.get("articles") or {}).get("results", [])

        signals: list[PublicSignal] = []
        for art in articles:
            headline = str(art.get("title") or f"Name/pivot event — {name}")
            lower = headline.lower()
            month = _date_str_to_month(
                str(art.get("dateTime", date_from))[:10], since_month
            )
            source_name = (art.get("source") or {}).get("title") or self.display_name
            is_name_change = any(k in lower for k in _NAME_CHANGE_KEYWORDS)
            signals.append(
                PublicSignal(
                    month=month,
                    signal_type="name_change" if is_name_change else "business_model_change",
                    headline=headline[:200],
                    severity=0.70 if is_name_change else 0.60,
                    source=source_name,
                    source_url=art.get("url"),
                )
            )
        return signals
