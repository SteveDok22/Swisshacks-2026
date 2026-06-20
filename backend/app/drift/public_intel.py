"""
Public Intelligence Layer (Layer 2) — external signals.

AMINA Challenge 4 asks for "real time public signals (news, sanctions lists,
adverse media, ownership changes, funding events)" combined with internal
bank data, in an explicit two-layer architecture (public first, then internal).

This module is the PUBLIC half. The internal half is BOCPD + velocity +
declared-consistency (already built). The DriftEngine fuses the two and — the
differentiator — computes a **Confirmation Lift**: how much a public signal
and an internal drift signal, co-occurring in time, raise confidence beyond
what either gives alone.

Design choice (hybrid, time-aligned):
- Drifting customers receive public signals that ALIGN IN TIME with their
  internal drift onset — modelling the real world, where a funding event or
  adverse-media story is the external shadow of the same structural change
  the transactions reveal.
- Stable customers receive only rare, low-severity background noise — the
  honest false-positive control.

Pure Python + a tiny lexicon-based severity classifier (no heavy NLP dep;
in production this slot takes an embedding classifier or an LLM call at T1/T2).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.drift.business_model import WEBSITE_COMPARISON_SOURCE
from app.sources.base import PublicSignal

if TYPE_CHECKING:
    from app.sources.cost import CostMixin

_logger = get_logger(__name__)

# Five public-signal categories named in the AMINA brief
SIGNAL_TYPES = (
    "news",
    "sanctions",
    "adverse_media",
    "ownership_change",
    "funding_event",
)

# Lexicon-based severity classifier. In production this is an embedding model;
# for the MVP a transparent keyword map is explainable and dependency-free.
_SEVERITY_LEXICON = {
    # high severity
    "sanction": 0.95, "indicted": 0.9, "laundering": 0.95, "fraud": 0.85,
    "shell company": 0.8, "offshore": 0.7, "investigation": 0.75,
    "undisclosed": 0.7, "regulator probe": 0.8, "frozen assets": 0.9,
    # medium
    "funding round": 0.45, "new investor": 0.4, "ownership change": 0.5,
    "acquisition": 0.4, "lawsuit": 0.55, "restructuring": 0.45,
    # low / benign
    "partnership": 0.2, "award": 0.1, "expansion": 0.2, "hiring": 0.1,
    "product launch": 0.15,
}

# PublicSignal is now defined in sources/base.py (canonical location) and
# imported above. The re-export keeps existing imports from this module working.
__all__ = ["PublicSignal", "elevate_corroborated_pivots"]

# --- UC 10: cross-source business-model-pivot corroboration ----------------
# Signal type emitted BOTH by news adapters (Event Registry primary / GDELT
# fallback, on a pivot/rebrand article cluster) AND by the website cosine
# comparator (drift/business_model.py, on Wayback↔Firecrawl distance ≥ 0.35).
_PIVOT_SIGNAL_TYPE = "business_model_change"
# A lone pivot headline is noise; a credible news *event cluster* needs at least
# this many independent news-derived pivot signals. Mirrors the adapters' own
# clustering (GDELT requires ≥ 3 articles; Event Registry emits one per article).
_NEWS_PIVOT_CLUSTER_MIN = 2
# Severity a corroborated pivot is elevated to — the top "near-certain escalation
# trigger" band (0.90–1.00) in docs/source-integration-architecture.md §5.
_CRITICAL_SEVERITY = 0.95
# Synthetic-scenario calibration (offline demo path only).
_PIVOT_NEWS_SEVERITY = 0.60     # matches Event Registry / GDELT pivot signals
_PIVOT_WEBSITE_DISTANCE = 0.52  # cosine distance, comfortably past the 0.35 threshold


def classify_severity(headline: str) -> float:
    """
    Lexicon severity classifier. Returns the max matched term weight, or a
    small base for unmatched (benign) text. Transparent and explainable —
    the matched term is the explanation.
    """
    h = headline.lower()
    best = 0.05  # benign baseline
    for term, weight in _SEVERITY_LEXICON.items():
        if term in h:
            best = max(best, weight)
    return best


# Headline templates per signal type, split by severity intent
_HEADLINES = {
    "adverse_media": [
        "Reuters: {name}-linked entity named in money laundering investigation",
        "Local press: regulator probe touches firm connected to {name}",
        "Trade outlet: undisclosed offshore structure tied to {name}",
    ],
    "funding_event": [
        "{name}'s holding company closes funding round led by new investor",
        "Press release: {name} entity receives capital injection from offshore fund",
        "Filing: new investor takes stake in {name}-controlled company",
    ],
    "ownership_change": [
        "Registry update: ownership change in {name}-linked shell company",
        "Corporate filing: new beneficial owner added to {name} structure",
        "{name} restructuring moves assets through intermediate holding",
    ],
    "sanctions": [
        "OFAC update: entity two hops from {name} added to SDN list",
        "EU sanctions list expands to counterparty linked to {name}",
    ],
    "news": [
        "{name} firm announces partnership expansion",
        "{name}-linked company product launch covered in trade press",
        "{name} entity announces new hiring in Zurich office",
    ],
    "business_model_change": [
        "{name} entity announces strategic pivot to a new product line",
        "Trade press: {name}-linked company rebrands around a new business model",
        "{name} firm shifts focus, unveils new product after strategic review",
    ],
}


_SOURCE_BASE_URLS = {
    "Reuters": "https://www.reuters.com/world/",
    "OFAC": "https://sanctionssearch.ofac.treas.gov/",
    "corporate registry": "https://www.zefix.admin.ch/",
    "press release": "https://example.com/demo-sources/press-release/",
    "trade press": "https://example.com/demo-sources/trade-press/",
}


def _demo_source_url(source: str, drift_id: str, signal_type: str, month: int) -> str:
    """
    Deterministic demo citation URL for synthetic public signals.

    Real source adapters can replace this with article, registry, or sanctions
    record URLs while preserving the API shape.
    """
    base = _SOURCE_BASE_URLS.get(source, "https://example.com/demo-sources/")
    slug = f"{drift_id}-{signal_type}-m{month}".lower().replace("_", "-")
    separator = "" if base.endswith("/") else "/"
    return f"{base}{separator}{slug}"


def generate_signals_for_customer(
    drift_id: str,
    name: str,
    scenario: str,
    months: int = 18,
    drift_start_month: int | None = None,
    seed: int | None = None,
) -> list[PublicSignal]:
    """
    Generate time-aligned public signals for one customer.

    Drifting customers get escalating, severity-rising signals starting around
    their internal drift onset; stable customers get sparse benign noise.
    """
    rng = np.random.default_rng(seed)
    signals: list[PublicSignal] = []

    first = name.split()[0]

    if scenario == "stable" or drift_start_month is None:
        # Sparse benign background noise — honest false-positive control
        n_noise = rng.integers(0, 3)
        for _ in range(int(n_noise)):
            m = int(rng.integers(0, months))
            headline = rng.choice(_HEADLINES["news"]).format(name=first)
            signals.append(
                PublicSignal(
                    month=m, signal_type="news", headline=headline,
                    severity=classify_severity(headline), source="trade press",
                    source_url=_demo_source_url("trade press", drift_id, "news", m),
                )
            )
        return sorted(signals, key=lambda s: s.month)

    if scenario == "news_spike":
        # UC 1 — reputational risk. Adverse media begins at the drift onset and
        # KEEPS accumulating month after month (the Wirecard pattern: red flags
        # pile up in public signals long before collapse), not a one-day blip.
        # The sustained run gives the weekly event-count series in the service
        # layer a genuine BOCPD regime change (see detect_news_spike_month).
        for month in range(drift_start_month + 1, months):
            headline = rng.choice(_HEADLINES["adverse_media"]).format(name=first)
            signals.append(
                PublicSignal(
                    month=int(month), signal_type="adverse_media", headline=headline,
                    severity=classify_severity(headline), source="Reuters",
                    source_url=_demo_source_url("Reuters", drift_id, "adverse_media", month),
                )
            )
        return sorted(signals, key=lambda s: s.month)

    # Pivot scenario (UC 10, Centra Tech pattern): a public business-model pivot
    # that surfaces in two independent lenses at once — a NEWS pivot/rebrand
    # cluster and a WEBSITE cosine shift — alongside a co-occurring funding event.
    # elevate_corroborated_pivots() then lifts the corroborated pivot to the
    # critical band, exactly as the live aggregator does.
    if scenario == "pivot":
        pivot_signals: list[PublicSignal] = []
        pivot_month = min(drift_start_month + 1, months - 1)  # ~month 9 for the default onset
        # 1. News pivot/rebrand CLUSTER (one past the minimum, like real coverage).
        for offset in range(_NEWS_PIVOT_CLUSTER_MIN + 1):
            m = min(pivot_month + offset, months - 1)
            headline = rng.choice(_HEADLINES["business_model_change"]).format(name=first)
            pivot_signals.append(
                PublicSignal(
                    month=m, signal_type="business_model_change", headline=headline,
                    severity=_PIVOT_NEWS_SEVERITY, source="trade press",
                    source_url=_demo_source_url(
                        "trade press", drift_id, "business_model_change", m
                    ),
                )
            )
        # 2. Co-occurring funding event — the pivot is financed (Centra Tech's ICO raise).
        funding_headline = rng.choice(_HEADLINES["funding_event"]).format(name=first)
        pivot_signals.append(
            PublicSignal(
                month=pivot_month, signal_type="funding_event", headline=funding_headline,
                severity=classify_severity(funding_headline), source="press release",
                source_url=_demo_source_url(
                    "press release", drift_id, "funding_event", pivot_month
                ),
            )
        )
        # 3. Website cosine distance fires, mirroring drift/business_model.py's
        #    signal at distance ≥ 0.35 (severity = clip(0.20 + 1.30 × distance, 0, 0.95)).
        distance = _PIVOT_WEBSITE_DISTANCE
        severity = min(0.20 + 1.30 * distance, 0.95)
        pivot_signals.append(
            PublicSignal(
                month=pivot_month, signal_type="business_model_change",
                headline=(
                    f"Website content for {name} shifted materially since onboarding "
                    f"(cosine distance {distance:.2f})"
                ),
                severity=severity, source=WEBSITE_COMPARISON_SOURCE,
                source_url=_demo_source_url(
                    "website", drift_id, "business_model_change", pivot_month
                ),
            )
        )
        return elevate_corroborated_pivots(
            sorted(pivot_signals, key=lambda s: s.month)
        )

    # Drifting customer: signals align with and follow internal drift onset.
    # Earlier signals are softer (funding/ownership), later turn adverse.
    sig_plan = [
        (drift_start_month + 1, "funding_event", "press release"),
        (drift_start_month + 3, "ownership_change", "corporate registry"),
        (drift_start_month + 5, "adverse_media", "Reuters"),
    ]
    # combined scenario also draws a late sanctions-proximity signal
    if scenario == "combined":
        sig_plan.append((months - 2, "sanctions", "OFAC"))

    for month, stype, source in sig_plan:
        if month >= months:
            continue
        headline = rng.choice(_HEADLINES[stype]).format(name=first)
        signals.append(
            PublicSignal(
                month=int(month), signal_type=stype, headline=headline,
                severity=classify_severity(headline), source=source,
                source_url=_demo_source_url(source, drift_id, stype, int(month)),
            )
        )

    return sorted(signals, key=lambda s: s.month)


# --- News-volume regime detection (UC 1) ---------------------------------- #

# Sub-month buckets used when building the event-count series for BOCPD.
# Month-resolution signals are too coarse for the detector (its burn-in alone is
# 10 observations), so each month is sliced into weeks: an 18-month book becomes
# a ~72-point weekly series, long enough to surface a sustained spike.
_WEEKS_PER_MONTH = 4

# Signal types that count as "news volume" for the spike detector. Structural
# registry/web-change signals (name_change, ownership_change, ...) describe a
# discrete event, not a news-coverage volume, so they are excluded.
_NEWS_SIGNAL_TYPES = frozenset({"news", "adverse_media"})

# Minimum number of distinct months (from the changepoint onward) that must
# carry news for a regime change to count as a reputational spike. A genuine
# adverse-media campaign accumulates over time (Wirecard); a stable customer's
# sparse background noise (0-2 scattered stories) is a blip, not a spike — this
# guard is the detector's honest false-positive control.
_MIN_SPIKE_MONTHS = 3


def detect_news_spike_month(
    signals: list[PublicSignal],
    months: int,
    *,
    weeks_per_month: int = _WEEKS_PER_MONTH,
) -> int | None:
    """Detect a sustained news-volume regime change via BOCPD on event counts.

    Buckets the news / adverse-media signals into a weekly event-count series
    over the observation window and runs the same BOCPD detector the engine
    uses on internal transaction volume. A *sustained* rise in news coverage
    (adverse media that keeps accumulating) registers as a regime change; the
    first detected changepoint is mapped back to its month index and returned as
    ``news_spike_month``.

    Returns ``None`` when there is no news, no spike, or the series is degenerate
    — the honest no-signal control (a stable customer's sparse background noise
    must not read as a spike). Pure function; no I/O.
    """
    # Local import avoids a public_intel <-> drift module import cycle at startup.
    from app.drift.bocpd import BOCPD, standardize

    if not signals or months <= 0 or weeks_per_month < 1:
        return None

    weeks = months * weeks_per_month
    counts = np.zeros(weeks)
    for s in signals:
        if s.signal_type not in _NEWS_SIGNAL_TYPES:
            continue
        # A month-resolution signal raises the news volume for that whole month,
        # so it fills the month's week block. Clamp out-of-window months so a
        # stray index can never write past the grid.
        month = min(max(s.month, 0), months - 1)
        start = month * weeks_per_month
        counts[start : start + weeks_per_month] += 1.0

    if counts.sum() == 0.0:
        return None

    result = BOCPD(hazard=1 / 500).run(standardize(counts))
    if not result.detected_changepoints:
        return None
    spike_month = result.detected_changepoints[0] // weeks_per_month

    # Reject one-off blips: require news to persist for several months from the
    # changepoint onward (a sustained campaign, not a single scattered story).
    elevated_months = sum(
        1
        for month in range(spike_month, months)
        if counts[month * weeks_per_month] > 0.0
    )
    if elevated_months < _MIN_SPIKE_MONTHS:
        return None
    return spike_month


def elevate_corroborated_pivots(signals: list[PublicSignal]) -> list[PublicSignal]:
    """Elevate a business-model pivot to *critical* when two independent sources confirm it (UC 10).

    A public business-model pivot (the Centra Tech pattern: a debit-card fintech
    that became an ICO in 90 days) is only high-confidence when it shows up in two
    *independent* lenses at once:

    1. a **news** pivot/rebrand event cluster — ``business_model_change`` signals
       whose source is a news outlet (Event Registry primary, GDELT fallback), and
    2. a **website** cosine shift — a ``business_model_change`` signal from
       ``drift/business_model.py``, which only fires when the Wayback↔Firecrawl
       cosine distance clears ``BUSINESS_MODEL_DISTANCE_THRESHOLD`` (0.35). Its
       mere presence in the list therefore *is* the "distance ≥ 0.35" condition.

    When both lenses are present (≥ ``_NEWS_PIVOT_CLUSTER_MIN`` news pivots AND
    ≥ 1 website pivot) the two corroborate each other, so every pivot signal is
    elevated to the critical band. Either lens alone is left untouched — one
    source is a lead, not a confirmation. The input list is never mutated:
    ``PublicSignal`` is frozen, so elevated signals are fresh copies and order is
    preserved.
    """
    pivots = [s for s in signals if s.signal_type == _PIVOT_SIGNAL_TYPE]
    if not pivots:
        return signals

    website_pivots = [s for s in pivots if s.source == WEBSITE_COMPARISON_SOURCE]
    news_pivots = [s for s in pivots if s.source != WEBSITE_COMPARISON_SOURCE]
    # Need BOTH independent lenses: a news event cluster AND the website cosine
    # shift. One alone is a lead, not a corroboration — leave severities as-is.
    if not website_pivots or len(news_pivots) < _NEWS_PIVOT_CLUSTER_MIN:
        return signals

    _logger.info(
        "pivot_corroborated_critical",
        news_pivots=len(news_pivots),
        website_pivots=len(website_pivots),
    )
    return [
        replace(s, severity=max(s.severity, _CRITICAL_SEVERITY))
        if s.signal_type == _PIVOT_SIGNAL_TYPE
        else s
        for s in signals
    ]


@dataclass
class PublicIntelResult:
    """Aggregate public-intelligence assessment for one customer."""

    signals: list[PublicSignal] = field(default_factory=list)
    # Aggregate public risk 0..1 (severity-weighted, recency-weighted)
    public_risk: float = 0.0
    # Month of the strongest signal (for co-occurrence with internal drift)
    peak_signal_month: int | None = None


def assess_public_risk(signals: list[PublicSignal], months: int = 18) -> PublicIntelResult:
    """
    Aggregate signals into a public-risk score.

    Severity-weighted with mild recency weighting (recent signals matter more).
    """
    if not signals:
        return PublicIntelResult()

    total = 0.0
    weight_sum = 0.0
    peak_sev = -1.0
    peak_month = None
    for s in signals:
        recency = 0.5 + 0.5 * (s.month / max(months - 1, 1))  # 0.5..1.0
        contrib = s.severity * recency
        total += contrib
        weight_sum += recency
        if s.severity > peak_sev:
            peak_sev = s.severity
            peak_month = s.month

    # Normalize: a single max-severity recent signal approaches ~0.95
    public_risk = min(total / max(weight_sum, 1.0), 1.0) if weight_sum else 0.0
    # Boost if multiple high-severity signals stack
    high_sev_count = sum(1 for s in signals if s.severity >= 0.7)
    public_risk = min(public_risk + 0.1 * max(high_sev_count - 1, 0), 1.0)

    return PublicIntelResult(
        signals=signals,
        public_risk=public_risk,
        peak_signal_month=peak_month,
    )


# Per-adapter wall-clock cap. Bounds each adapter INDEPENDENTLY so one slow
# source is dropped on its own (returns []) while every other source's results
# survive — the aggregation degrades partially, never all-or-nothing.
_PER_ADAPTER_TIMEOUT_S: float = 15.0

# Backstop wall-clock cap for one full aggregation round (all adapters in
# parallel). With per-adapter caps in place this only fires in pathological
# cases (e.g. an adapter that ignores cancellation); it returns [] as a last
# resort. Kept strictly above _PER_ADAPTER_TIMEOUT_S so the per-adapter path
# is what normally trims slow sources.
_AGGREGATE_TIMEOUT_S: float = 25.0

# Ceiling for gather_public_signals_sync's thread join.  Set slightly above
# _AGGREGATE_TIMEOUT_S so the async layer always cancels first, giving adapters
# a chance to run their finally/aclose blocks before the thread is abandoned.
_SYNC_TIMEOUT_S: float = 30.0

# Cap on how many GLEIF direct-child LEIs are resolved + screened per customer
# (Case 5). Ownership chains fan out fast; resolving every child is one extra
# GLEIF call each and unnecessary for a risk signal — the first N are screened.
_MAX_UBO_CHILDREN: int = 10


async def _resolve_lei_name(adapter: Any, drift_id: str, lei: str) -> str | None:
    """Resolve one LEI to its legal name via GLEIF. Best-effort → None on error.

    Not individually time-bounded: the whole resolution is wrapped in a single
    wall-clock budget by the caller (see ``gather_public_signals``).
    """
    try:
        snap = await adapter.fetch(drift_id, lei, lei=lei)
    except Exception:  # noqa: BLE001 — one unresolvable LEI never sinks the rest
        return None
    return snap.name if snap and snap.name else None


async def _resolve_ubo_names(
    drift_id: str,
    name: str,
    adapters: tuple[Any, ...],
) -> list[str]:
    """Resolve the entity's GLEIF child LEIs to legal names for UBO screening.

    Case 5 (new shareholders / UBOs): the OpenSanctions adapter screens each
    name passed via its ``ubo_names`` kwarg. The names come from the GLEIF
    ownership chain — we fetch the entity's direct-child LEIs (the GLEIF adapter
    stores them in ``EntitySnapshot.officers``) and resolve each LEI back to a
    legal name.

    Returns ``[]`` when GLEIF is not among the usable adapters, the entity is
    not in GLEIF, or any error occurs — screening then degrades to the main
    entity only. Locating GLEIF by ``source_name`` (rather than importing the
    class) keeps this step inert whenever the registry is patched to a mock set
    without GLEIF, e.g. in the aggregator unit tests.
    """
    gleif_cls = next((a for a in adapters if a.source_name == "gleif"), None)
    if gleif_cls is None:
        return []

    adapter: Any = None
    try:
        adapter = gleif_cls()
        snapshot = await adapter.fetch(drift_id, name)
        if snapshot is None:
            return []
        # GLEIF stores direct-child LEIs in ``officers`` (no subsidiaries field
        # exists on EntitySnapshot). Cap the fan-out before resolving names.
        child_leis = [lei for lei in snapshot.officers if lei][:_MAX_UBO_CHILDREN]
        if not child_leis:
            return []
        resolved = await asyncio.gather(
            *(_resolve_lei_name(adapter, drift_id, lei) for lei in child_leis)
        )
        # Drop unresolved (None) names; dedupe while preserving order.
        return list(dict.fromkeys(n for n in resolved if n))
    except Exception as exc:  # noqa: BLE001 — UBO resolution is best-effort
        _logger.warning("public_intel_ubo_resolve_error", error=str(exc))
        return []
    finally:
        if adapter is not None and hasattr(adapter, "aclose"):
            try:
                await adapter.aclose()
            except Exception as exc:  # noqa: BLE001
                _logger.debug("public_intel_ubo_aclose_error", error=str(exc))


# The two news adapters are mutually exclusive: Event Registry is the
# entity-aware PRIMARY (needs a key), GDELT the always-free FALLBACK. Running
# both would double-count the same news-volume spike, so the aggregator keeps
# exactly one — selected at the single call site below.
_PRIMARY_NEWS_SOURCE = "event_registry"
_FALLBACK_NEWS_SOURCE = "gdelt"


def _select_news_source(
    adapters: tuple[type[CostMixin], ...],
) -> tuple[type[CostMixin], ...]:
    """Collapse the two news adapters to a single primary-vs-fallback choice.

    Event Registry when ``EVENT_REGISTRY_API_KEY`` is set, GDELT otherwise. The
    non-selected news adapter is dropped from the dispatch list; every other
    (non-news) adapter passes through untouched.
    """
    drop = (
        _FALLBACK_NEWS_SOURCE
        if settings.event_registry_api_key
        else _PRIMARY_NEWS_SOURCE
    )
    return tuple(a for a in adapters if a.source_name != drop)


async def gather_public_signals(
    drift_id: str,
    name: str,
    **kwargs: Any,
) -> list[PublicSignal]:
    """
    Dispatch fetch_signals() to all usable adapters in parallel and aggregate.

    Exactly one news source runs (see :func:`_select_news_source`): Event
    Registry when its key is set, GDELT as the free fallback otherwise.

    Each adapter is instantiated fresh per call and closed after use. Errors in
    individual adapters are caught so one failing source never blocks the rest.
    Returns a combined, time-sorted list of PublicSignals. Callers may pass
    ``since_month`` for incremental updates (forwarded to every adapter).

    A ``_AGGREGATE_TIMEOUT_S``-second wall-clock cap bounds the total call even
    when individual adapter timeouts are bypassed (e.g. blocking GDELT calls).
    """
    from app.sources.registry import usable_adapters  # local import avoids circular

    adapters = _select_news_source(usable_adapters())

    # Case 5: resolve UBO names from the GLEIF ownership chain so the
    # OpenSanctions adapter screens each one (its ``ubo_names`` kwarg). Skipped
    # when the caller already supplied ``ubo_names`` or GLEIF is not usable.
    # Best-effort — a resolution failure degrades to main-entity screening only
    # and never blocks the other adapters. The whole resolution (root fetch +
    # per-child name lookups) is bounded to one adapter's wall-clock budget so it
    # cannot, by itself, push the aggregation past the sync-bridge ceiling.
    if "ubo_names" not in kwargs:
        try:
            ubo_names = await asyncio.wait_for(
                _resolve_ubo_names(drift_id, name, adapters),
                timeout=_PER_ADAPTER_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001 — incl. TimeoutError; never blocks the rest
            _logger.warning("public_intel_ubo_resolve_timeout", error=str(exc))
            ubo_names = []
        if ubo_names:
            kwargs = {**kwargs, "ubo_names": ubo_names}

    async def _safe_fetch(cls: type[CostMixin]) -> list[PublicSignal]:
        # Construction is inside the guard too: an adapter __init__ that raises
        # must not sink the whole aggregation — it degrades like a fetch error.
        adapter: Any = None
        try:
            adapter = cls()
            return await asyncio.wait_for(
                adapter.fetch_signals(drift_id, name, **kwargs),
                timeout=_PER_ADAPTER_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001 — incl. TimeoutError; one source never sinks the rest
            _logger.warning(
                "public_intel_adapter_error",
                adapter=cls.source_name,
                error=str(exc),
            )
            return []
        finally:
            if adapter is not None and hasattr(adapter, "aclose"):
                try:
                    await adapter.aclose()
                except Exception as exc:  # noqa: BLE001
                    _logger.debug(
                        "public_intel_aclose_error",
                        adapter=cls.source_name,
                        error=str(exc),
                    )

    try:
        batches = await asyncio.wait_for(
            asyncio.gather(*[_safe_fetch(cls) for cls in adapters]),
            timeout=_AGGREGATE_TIMEOUT_S,
        )
    except TimeoutError:
        _logger.warning(
            "public_intel_aggregate_timeout",
            timeout_s=_AGGREGATE_TIMEOUT_S,
        )
        return []

    signals: list[PublicSignal] = [s for batch in batches for s in batch]
    # Cross-source corroboration (UC 10): a news pivot cluster + a website cosine
    # shift together elevate the pivot to critical before the merged list returns.
    return elevate_corroborated_pivots(sorted(signals, key=lambda s: s.month))


def gather_public_signals_sync(
    drift_id: str,
    name: str,
    **kwargs: Any,
) -> list[PublicSignal]:
    """
    Synchronous bridge for gather_public_signals().

    Runs the async aggregator in a dedicated thread with its own event loop so
    it is safe to call from synchronous DriftEngine methods even when FastAPI's
    own event loop is running in the current thread.

    ``_SYNC_TIMEOUT_S`` (slightly above the async ``_AGGREGATE_TIMEOUT_S``) caps
    the thread join so a completely unresponsive thread cannot block indefinitely.
    Returns ``[]`` on timeout rather than raising, matching the graceful-degradation
    contract of all other adapter error paths.

    NOTE: the executor is shut down with ``wait=False`` so a genuinely hung worker
    never re-blocks the caller on context-manager exit (``shutdown(wait=True)``
    would join it). An abandoned worker unwinds on its own once the inner
    ``_AGGREGATE_TIMEOUT_S`` cancels the aggregation.
    """
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(asyncio.run, gather_public_signals(drift_id, name, **kwargs))
    try:
        return future.result(timeout=_SYNC_TIMEOUT_S)
    except concurrent.futures.TimeoutError:
        _logger.warning(
            "public_intel_sync_timeout",
            timeout_s=_SYNC_TIMEOUT_S,
        )
        return []
    except Exception:  # noqa: BLE001 — honour the graceful-degradation contract
        # future.result() re-raises anything the worker raised (e.g. a bad
        # adapter import in usable_adapters()). The engine has no guard around
        # this call, so a failure here must degrade to [] rather than crash the
        # whole scan loop.
        _logger.exception("public_intel_sync_error")
        return []
    finally:
        pool.shutdown(wait=False)


def confirmation_lift(
    public_risk: float,
    internal_risk: float,
    public_peak_month: int | None,
    internal_peak_month: int | None,
    *,
    coincidence_window: int = 3,
) -> float:
    """
    Confirmation Lift — the differentiator.

    Two weak, independent signals that co-occur in time provide more evidence
    together than the product of their parts. We model:

        Lift = P(risk | public AND internal)
               -----------------------------------------
               P(risk | public) * P(risk | internal)

    approximated as the ratio of the joint (boosted by temporal coincidence)
    to the independent product. Lift > 1 means the two worlds CONFIRM each
    other; Lift ~ 1 means they are unrelated.

    Temporal coincidence: if the peak public signal and the peak internal
    drift fall within `coincidence_window` months, the joint is amplified —
    because the external story and the internal behaviour are plausibly the
    same underlying event seen from two sides.
    """
    p = max(min(public_risk, 0.99), 1e-3)
    q = max(min(internal_risk, 0.99), 1e-3)

    # Confirmation Lift is only meaningful when BOTH worlds carry real signal.
    # When either side is negligible there is nothing to "confirm" — two
    # near-zero risks coinciding is not evidence, it is the absence of it.
    # We gate the lift to the regime where both p and q clear a floor; below
    # it, lift is neutral (1.0). This avoids the divide-by-near-zero artifact
    # that would otherwise report a meaningless 1000x lift on quiet customers.
    SIGNAL_FLOOR = 0.15
    if public_risk < SIGNAL_FLOOR or internal_risk < SIGNAL_FLOOR:
        return 1.0

    # Temporal coincidence factor in [1, 2]
    coincidence = 1.0
    if public_peak_month is not None and internal_peak_month is not None:
        gap = abs(public_peak_month - internal_peak_month)
        if gap <= coincidence_window:
            coincidence = 2.0 - (gap / coincidence_window)  # 1.0 .. 2.0

    # Joint probability under positive dependence (noisy-OR style), then
    # amplified by temporal coincidence
    independent_product = p * q
    joint = min(p + q - p * q, 0.99) * coincidence
    joint = min(joint, 0.999)

    if independent_product < 1e-6:
        return 1.0
    return joint / independent_product
