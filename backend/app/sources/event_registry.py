"""
Event Registry / NewsAPI.ai — structured news event aggregation.

WHAT IT PROVIDES
    News clustered into de-duplicated *events* (20-50 articles → one Event),
    which makes spike detection robust against syndication/SEO noise.
    Entity-aware queries return events *about* a named company rather than
    simple keyword matches. Each result carries a relevance score, event
    sentiment, and article-level source quality rating.

WHY WE NOW IMPLEMENT IT  →  hackathon API key provided
    Previously skipped as trial-only. SwissHacks 2026 hackathon provides an
    API key with full access. This is now the PRIMARY news source for Cases 1,
    6, 8, 10; :class:`app.sources.gdelt.GdeltAdapter` remains as a free
    fallback when the key is absent.

    Base URL:   https://eventregistry.org/api/v1/  (a.k.a. newsapi.ai)
    Auth:       ``?apiKey={EVENT_REGISTRY_API_KEY}`` query param or
                ``"apiKey": key`` in POST body.
    Key env:    ``EVENT_REGISTRY_API_KEY``
    Rate limit: 2,500 requests / day on hackathon tier; no per-second limit.

    Key endpoints (all POST, JSON body):
        /article/getArticles   — articles about entity (last N days)
        /event/getEvents       — clustered events about entity
        /event/getEvent        — single event detail + article list
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class EventRegistryAdapter(CostMixin, RegistryAdapter):
    """Structured news-event aggregation — primary news source (hackathon key)."""

    source_name = "event_registry"
    display_name = "Event Registry / NewsAPI.ai"
    base_url = "https://eventregistry.org/api/v1"
    docs_url = "https://newsapi.ai/documentation"
    cost = SourceCost.PAID
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (1, 6, 8, 10)
    signal_types = ("news", "adverse_media", "funding_event", "business_model_change")

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
