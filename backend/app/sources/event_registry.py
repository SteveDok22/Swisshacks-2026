"""
Event Registry / NewsAPI.ai — news EVENT aggregation.   *** SKIPPED: PAID ***

WHAT IT WOULD PROVIDE
    News clustered into de-duplicated *events* (20-50 articles -> one Event),
    which makes spike detection robust against syndication/SEO noise — nicer
    than raw article counts for the Case 1 negative-news-spike use case.

WHY WE SKIP IT  →  FREEMIUM-but-trial-only, treated as PAID (status = SKIPPED)
    Free registration grants only a ONE-TIME ~2,000-token allowance over the
    recent-30-day window; it does not renew. That is a trial, not a sustainable
    free tier, so for a live demo it is effectively paid. We mark it PAID and
    skip it.

    Replacement: :class:`app.sources.gdelt.GdeltAdapter` is FREE, key-less, and
    covers the same Cases (1, 6, 8, 10) via article lists + volume time-series.
    Event-level clustering is a "nice to have" we forego to stay 100% free.

    Would-be base URL: https://eventregistry.org/api/v1/  (a.k.a. newsapi.ai)
    ``fetch`` raises :class:`SourceUnavailableError` via ``_carcass``.
"""

from __future__ import annotations

from app.sources.base import AdapterStatus, EntitySnapshot, RegistryAdapter, SourceCost


class EventRegistryAdapter(RegistryAdapter):
    """News-event aggregation — SKIPPED (trial-only; use GDELT instead)."""

    source_id = "event_registry"
    display_name = "Event Registry / NewsAPI.ai"
    base_url = "https://eventregistry.org/api/v1"
    docs_url = "https://newsapi.ai/documentation"
    cost = SourceCost.PAID
    status = AdapterStatus.SKIPPED
    requires_api_key = True
    use_cases = (1, 6, 8, 10)
    signal_types = ("news", "adverse_media", "funding_event")

    def fetch(self, entity_id: str) -> dict:
        self._carcass()  # raises SourceUnavailableError (paid/skipped)
        raise AssertionError("unreachable")  # pragma: no cover

    def normalize(self, raw: dict) -> EntitySnapshot:
        self._carcass()
        raise AssertionError("unreachable")  # pragma: no cover
