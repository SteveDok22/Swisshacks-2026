"""
GDELT 2.0 (DOC 2.0 API) — global news monitoring.  FREE news alternative.

WHAT IT PROVIDES
    Worldwide news article search over a rolling window with article lists
    (``mode=artlist``) and volume time-series (``mode=timelinevol``), filterable
    by entity/keyword, language and tone. No key, no cost.

WHY IT MATTERS HERE  (Use cases 1, 6, 8, 10)
    The sustainable, free replacement for the (paid) Event Registry adapter. The
    article/volume time-series per customer feeds BOCPD on the news count (Case 1
    negative-news spike); article tone seeds the ``news`` / ``adverse_media``
    severity; coverage of a funding/expansion event corroborates Case 6. The
    signal is a time-series, so this adapter only implements ``fetch_signals``
    (``fetch`` returns ``None`` — GDELT has no canonical entity record).

COST / ACCESS  →  FREE, no API key
    Base URL:  https://api.gdeltproject.org/api/v2/doc/doc
    We talk to it through the ``gdeltdoc`` client (synchronous; wrapped in
    ``asyncio.to_thread``), which builds the query string, sends a User-Agent,
    and parses the JSON into a pandas DataFrame.

HOW THIS ADAPTER WORKS  (verified live against the real API, June 2026)
    ``fetch_signals(name)`` runs two independent modes concurrently and merges
    their signals; ``fetch()`` always returns ``None`` (no canonical record):

    1. News-volume regime change (UC 1) — ``_news_volume_signals``
         GET timeline mode ``timelinevolraw`` over ``_VOLUME_TIMESPAN`` (12m).
         Real response columns: ``["datetime", "Article Count", "All Articles"]``
         → ~354 *daily* points/yr. We z-score the "Article Count" series
         (``standardize``) and run BOCPD; each detected changepoint becomes one
         signal. We then pull ``timelinetone`` for that index and map average
         tone (≈ −10..+10) to severity: negative tone → ``adverse_media``
         (severity ≥ 0.65), otherwise ``news``. Deduped to one signal per month.
    2. Funding + pivot from headlines (UC 6 / UC 10) — ``_article_signals``
         One ``article_search`` over ``_ARTICLE_TIMESPAN`` (3m, ``_ARTICLE_RECORDS``
         rows). Real columns: ``url, url_mobile, title, seendate, socialimage,
         domain, language, sourcecountry``. Each title is keyword-classified:
         a funding hit → ``funding_event``; pivot/rebrand hits → a
         ``business_model_change`` *only* when ≥ ``_PIVOT_CLUSTER_MIN`` (3) of
         them fall inside a ~60-day window (``_has_pivot_cluster``) — a lone
         "pivot" headline is ignored as noise.

    ``seendate`` arrives as ``YYYYMMDDTHHMMSSZ`` (e.g. ``20260614T090000Z``) and
    each article/changepoint date is bucketed into the engine's 0..11 month
    index (~30-day steps), clamped to ``[since_month, 11]``.

LIMITATIONS — READ BEFORE RELYING ON THIS (GDELT is an obscure, quirky API)
    * Rate limiting is the #1 failure mode. GDELT throttles to roughly
      1 request / 5 s per IP; a burst raises ``gdeltdoc.errors.RateLimitError``
      (a ``requests.HTTPError`` subclass). Each ``fetch_signals`` issues up to 3
      calls (volraw + tone + article), two of them concurrently — so under load
      one or more can be throttled. By design every query is wrapped so a
      throttle/timeout/HTML error degrades to ``[]`` rather than raising: the
      adapter NEVER crashes, but it can silently return PARTIAL or NO signals.
      It is a best-effort *fallback*, not a guaranteed feed. If you need
      reliable volume signals, space calls out or add backoff at the caller.
    * Coverage skews to major media. GDELT indexes large/online news, so a
      small or private KYC subject (the common case for a bank) often has
      near-zero coverage → no signals. Tested on "Wirecard" (well covered) the
      volume series is real but sparse now (the scandal peaked in 2020).
    * Keyword search, not entity resolution. ``Filters(keyword=name)`` is plain
      text matching — common names produce false positives; it does not
      disambiguate by concept/URI the way Event Registry does. That is exactly
      why Event Registry is the PRIMARY source and GDELT only the free fallback.
    * Month mapping is approximate (~30-day buckets), and ``article_search``
      reliably reaches back only ~3 months, so funding/pivot signals land in
      recent months regardless of ``since_month``.
    * Tone is GDELT's own average-tone metric, not a calibrated sentiment model;
      treat the news/adverse_media split as a coarse heuristic.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

from gdeltdoc import Filters, GdeltDoc

from app.drift.bocpd import BOCPD, standardize
from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

logger = logging.getLogger(__name__)

# GDELT timeline modes officially support spans longer than 3 months; article
# list (artlist) only reliably covers the most recent ~3 months. gdeltdoc
# rejects a "y" unit, so the year-long window is expressed as "12m".
_VOLUME_TIMESPAN = "12m"
_ARTICLE_TIMESPAN = "3m"
_ARTICLE_RECORDS = 75

# BOCPD needs more points than its burn-in to detect a regime change; below this
# the volume series is too short to be meaningful.
_MIN_TIMELINE_POINTS = 12

# Title-keyword vocabularies (kept aligned with EventRegistryAdapter so the
# primary source and its fallback classify the same news the same way).
_FUNDING_KEYWORDS = ("funding", "investment", "raised", "capital raise", "ipo")
_PIVOT_KEYWORDS = (
    "pivot",
    "rebrand",
    "rebranding",
    "renamed",
    "new product",
    "business model",
    "strategic shift",
)

# A business-model pivot is only credible as a *cluster* of coverage, not one
# stray headline — ROADMAP: >= 3 articles within a ~60-day (2-month) window.
_PIVOT_CLUSTER_MIN = 3
_PIVOT_CLUSTER_WINDOW_MONTHS = 2

# Severity calibration (PublicSignal.severity is a float in [0, 1]).
_ADVERSE_FLOOR = 0.65  # news vs. adverse_media split (mirrors EventRegistry)
_FUNDING_SEVERITY = 0.55
_PIVOT_SEVERITY = 0.60
_SEVERITY_TONE_VERY_NEG = 0.85
_SEVERITY_TONE_NEG = 0.65
_SEVERITY_TONE_MILD_NEG = 0.50
_SEVERITY_TONE_NEUTRAL = 0.35
_SEVERITY_TONE_UNKNOWN = 0.50

# Columns that carry the time axis / normalisation, never the data series.
_TIMELINE_NON_SERIES = frozenset({"datetime", "All Articles"})


def _tone_to_severity(tone: float | None) -> float:
    """Map a GDELT average-tone value (≈ −10 negative … +10 positive) to severity.

    A detected volume regime change is itself notable, so even neutral/positive
    coverage yields a non-zero ``news`` severity; negative tone escalates it
    toward ``adverse_media``.
    """
    if tone is None:
        return _SEVERITY_TONE_UNKNOWN
    if tone <= -5.0:
        return _SEVERITY_TONE_VERY_NEG
    if tone <= -2.0:
        return _SEVERITY_TONE_NEG
    if tone < 0.0:
        return _SEVERITY_TONE_MILD_NEG
    return _SEVERITY_TONE_NEUTRAL


def _series_column(columns: Any) -> str | None:
    """Return the first data-series column of a timeline DataFrame.

    GDELT labels the series itself (``"Article Count"``, ``"Average Tone"``);
    selecting by exclusion keeps the parser robust to those labels changing.
    """
    for col in columns:
        if col not in _TIMELINE_NON_SERIES:
            return str(col)
    return None


def _parse_seendate(raw: Any) -> datetime | None:
    """Parse a GDELT ``seendate`` (``YYYYMMDDTHHMMSSZ``) into an aware datetime."""
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _date_to_month(when: datetime | None, since_month: int) -> int:
    """Map an absolute date to the engine's 0..11 month index.

    Newest coverage maps toward month 11; each ~30 days back steps one month
    earlier. The result is clamped to ``[since_month, 11]`` so callers requesting
    an incremental window never receive an earlier month than they asked for.
    """
    if when is None:
        return max(0, min(11, since_month))
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta_days = (datetime.now(UTC) - when).days
    month = max(0, 11 - delta_days // 30)
    return max(since_month, min(11, month))


def _has_pivot_cluster(months: list[int]) -> bool:
    """True when >= _PIVOT_CLUSTER_MIN pivot articles fall in a ~60-day window."""
    if len(months) < _PIVOT_CLUSTER_MIN:
        return False
    ordered = sorted(months)
    for i in range(len(ordered) - _PIVOT_CLUSTER_MIN + 1):
        window = ordered[i : i + _PIVOT_CLUSTER_MIN]
        if window[-1] - window[0] <= _PIVOT_CLUSTER_WINDOW_MONTHS:
            return True
    return False


class GdeltAdapter(CostMixin, RegistryAdapter):
    """GDELT 2.0 news-monitoring connector — free, always-on fallback.

    Implements ``fetch_signals`` only (``fetch`` returns ``None`` — GDELT has no
    canonical entity record). Every external call is wrapped in
    ``asyncio.to_thread`` because ``gdeltdoc`` is synchronous, and each detection
    mode is isolated so one failing query never sinks the others.

    Parameters
    ----------
    client:
        Optional injected ``gdeltdoc.GdeltDoc`` (tests pass a stub). A default
        instance is created otherwise; ``GdeltDoc()`` performs no I/O on init.
    """

    source_name = "gdelt"
    display_name = "GDELT 2.0 (news)"
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    docs_url = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (1, 6, 8, 10)
    signal_types = ("news", "adverse_media", "funding_event", "business_model_change")

    def __init__(self, client: GdeltDoc | None = None) -> None:
        self._gd: GdeltDoc = client if client is not None else GdeltDoc()

    def record_url(self, entity_id: str) -> str | None:
        """Reproducible GDELT DOC volume-timeline link for ``entity_id`` (a name)."""
        if not entity_id:
            return None
        query = quote_plus(f'"{entity_id}"')
        return (
            f"{self.base_url}?query={query}"
            f"&mode=timelinevolraw&format=html&timespan={_VOLUME_TIMESPAN}"
        )

    # ------------------------------------------------------------------
    # Public contract
    # ------------------------------------------------------------------

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        """GDELT is a news source only — no canonical entity record."""
        return None

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        """Fetch free GDELT news signals for *name*.

        Two detection modes run concurrently:

        - **news volume (UC 1)** — raw weekly/daily article counts → BOCPD →
          a ``news`` / ``adverse_media`` signal at each detected regime change,
          severity from average tone.
        - **funding (UC 6) + pivot (UC 10)** — one article search whose titles are
          classified into ``funding_event`` and (when a cluster forms)
          ``business_model_change`` signals.

        Returns ``[]`` (never raises) for a blank name, empty results, or any
        gdeltdoc / network error — GDELT is a best-effort fallback.
        """
        if not name or not name.strip():
            return []
        name = name.strip()
        since_month = max(0, min(11, since_month))

        results = await asyncio.gather(
            self._news_volume_signals(name, since_month),
            self._article_signals(name, since_month),
            return_exceptions=True,
        )

        signals: list[PublicSignal] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("gdelt mode failed for %r: %s", name, result)
                continue
            signals.extend(result)
        return signals

    # ------------------------------------------------------------------
    # Detection modes
    # ------------------------------------------------------------------

    async def _news_volume_signals(
        self, name: str, since_month: int
    ) -> list[PublicSignal]:
        """UC 1 — BOCPD over the raw article-count timeline."""
        vol_df = await self._safe_timeline("timelinevolraw", name)
        if vol_df is None or vol_df.empty:
            return []
        counts_col = _series_column(vol_df.columns)
        if counts_col is None or "datetime" not in vol_df.columns:
            return []

        counts = vol_df[counts_col].to_numpy(dtype=float)
        if counts.size < _MIN_TIMELINE_POINTS:
            return []

        result = BOCPD().run(standardize(counts))
        if not result.detected_changepoints:
            return []

        # timelinevolraw and timelinetone are SEPARATE GDELT calls that can
        # return different row counts / bucketing, so the volume changepoint
        # index must NOT be used to index tone positionally — align by date.
        tone_df = await self._safe_timeline("timelinetone", name)
        tone_by_day = _build_tone_index(tone_df)
        dates = vol_df["datetime"].tolist()

        signals: list[PublicSignal] = []
        seen_months: set[int] = set()
        for cp in result.detected_changepoints:
            if not 0 <= cp < len(dates):
                continue
            when = _as_datetime(dates[cp])
            month = _date_to_month(when, since_month)
            if month in seen_months:
                continue
            seen_months.add(month)

            tone = _tone_for(tone_by_day, when)
            severity = _tone_to_severity(tone)
            tone_note = f", avg_tone={tone:.1f}" if tone is not None else ""
            signals.append(
                PublicSignal(
                    month=month,
                    signal_type="adverse_media" if severity >= _ADVERSE_FLOOR else "news",
                    headline=(
                        f"GDELT news-volume regime change for {name}{tone_note}"
                    )[:200],
                    severity=severity,
                    source=self.display_name,
                    source_url=self.record_url(name),
                )
            )
        return signals

    async def _article_signals(
        self, name: str, since_month: int
    ) -> list[PublicSignal]:
        """UC 6 (funding) + UC 10 (pivot) — classify article titles."""
        df = await self._safe_articles(name)
        if df is None or df.empty or "title" not in df.columns:
            return []

        funding: list[PublicSignal] = []
        pivot_articles: list[tuple[int, str, str | None, str]] = []
        for row in df.itertuples(index=False):
            title = _clean_str(getattr(row, "title", None))
            if not title:
                continue
            lower = title.lower()
            url = _clean_str(getattr(row, "url", None))
            month = _date_to_month(_parse_seendate(getattr(row, "seendate", "")), since_month)
            source = _clean_str(getattr(row, "domain", None)) or self.display_name

            if any(kw in lower for kw in _FUNDING_KEYWORDS):
                funding.append(
                    PublicSignal(
                        month=month,
                        signal_type="funding_event",
                        headline=title[:200],
                        severity=_FUNDING_SEVERITY,
                        source=source,
                        source_url=url,
                    )
                )
            if any(kw in lower for kw in _PIVOT_KEYWORDS):
                pivot_articles.append((month, title, url, source))

        signals = list(funding)
        if _has_pivot_cluster([m for m, _, _, _ in pivot_articles]):
            for month, title, url, source in pivot_articles:
                signals.append(
                    PublicSignal(
                        month=month,
                        signal_type="business_model_change",
                        headline=title[:200],
                        severity=_PIVOT_SEVERITY,
                        source=source,
                        source_url=url,
                    )
                )
        return signals

    # ------------------------------------------------------------------
    # gdeltdoc wrappers — synchronous library calls pushed to a worker thread.
    # Each swallows its own errors and returns None so a single failing query
    # degrades to "no signals" rather than an exception.
    # ------------------------------------------------------------------

    async def _safe_timeline(self, mode: str, name: str) -> Any | None:
        try:
            return await asyncio.to_thread(self._run_timeline, mode, name)
        except Exception as exc:  # noqa: BLE001 — gdeltdoc raises bare ValueError/requests errors
            logger.warning("gdelt %s failed for %r: %s", mode, name, exc)
            return None

    def _run_timeline(self, mode: str, name: str) -> Any:
        filters = Filters(keyword=name, timespan=_VOLUME_TIMESPAN)
        return self._gd.timeline_search(mode, filters)

    async def _safe_articles(self, name: str) -> Any | None:
        try:
            return await asyncio.to_thread(self._run_articles, name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("gdelt article_search failed for %r: %s", name, exc)
            return None

    def _run_articles(self, name: str) -> Any:
        filters = Filters(
            keyword=name, timespan=_ARTICLE_TIMESPAN, num_records=_ARTICLE_RECORDS
        )
        return self._gd.article_search(filters)


def _as_datetime(value: Any) -> datetime | None:
    """Coerce a pandas Timestamp / ISO string from a timeline into a datetime."""
    if value is None:
        return None
    to_pydatetime = getattr(value, "to_pydatetime", None)
    dt: datetime
    if callable(to_pydatetime):
        dt = to_pydatetime()
    elif isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value)[:19])
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _clean_str(value: Any) -> str | None:
    """Coerce a possibly-missing pandas cell to a clean string, or ``None``.

    pandas yields ``NaN`` (a *truthy* float) for empty cells, so plain
    truthiness (``value or default``) would turn a missing url/title/domain
    into the literal string ``"nan"``. We treat NaN and blanks as absent.
    """
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN (only value != itself)
        return None
    text = str(value).strip()
    return text or None


def _build_tone_index(tone_df: Any) -> dict[Any, float]:
    """Map each ``timelinetone`` observation to its calendar day.

    ``timelinevolraw`` (volume) and ``timelinetone`` are SEPARATE GDELT calls
    that can return different row counts or bucketing, so a volume-series index
    cannot be reused to read tone positionally. Keying by date lets the caller
    look up the tone for the day a changepoint actually occurred; a missing day
    simply yields no tone (severity falls back to "regime change, tone unknown").
    """
    if tone_df is None or getattr(tone_df, "empty", True):
        return {}
    if "datetime" not in tone_df.columns:
        return {}
    tone_col = _series_column(tone_df.columns)
    if tone_col is None:
        return {}
    index: dict[Any, float] = {}
    for dt_raw, tone_raw in zip(
        tone_df["datetime"].tolist(), tone_df[tone_col].tolist(), strict=False
    ):
        when = _as_datetime(dt_raw)
        if when is None:
            continue
        try:
            index[when.date()] = float(tone_raw)
        except (TypeError, ValueError):
            continue
    return index


def _tone_for(tone_index: dict[Any, float], when: datetime | None) -> float | None:
    """Date-aligned tone lookup for a changepoint at ``when`` (None if absent)."""
    if when is None or not tone_index:
        return None
    return tone_index.get(when.date())
