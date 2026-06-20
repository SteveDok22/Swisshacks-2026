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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.logging import get_logger
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
__all__ = ["PublicSignal"]


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


async def gather_public_signals(
    drift_id: str,
    name: str,
    **kwargs: Any,
) -> list[PublicSignal]:
    """
    Dispatch fetch_signals() to all usable adapters in parallel and aggregate.

    Each adapter is instantiated fresh per call and closed after use. Errors in
    individual adapters are caught so one failing source never blocks the rest.
    Returns a combined, time-sorted list of PublicSignals. Callers may pass
    ``since_month`` for incremental updates (forwarded to every adapter).

    A ``_AGGREGATE_TIMEOUT_S``-second wall-clock cap bounds the total call even
    when individual adapter timeouts are bypassed (e.g. blocking GDELT calls).
    """
    from app.sources.registry import usable_adapters  # local import avoids circular

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
            asyncio.gather(*[_safe_fetch(cls) for cls in usable_adapters()]),
            timeout=_AGGREGATE_TIMEOUT_S,
        )
    except TimeoutError:
        _logger.warning(
            "public_intel_aggregate_timeout",
            timeout_s=_AGGREGATE_TIMEOUT_S,
        )
        return []

    signals: list[PublicSignal] = [s for batch in batches for s in batch]
    return sorted(signals, key=lambda s: s.month)


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
