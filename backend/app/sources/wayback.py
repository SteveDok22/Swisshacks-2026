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

COST / ACCESS  →  FREE, no API key (PLANNED — implement now)
    Public best-effort service; no SLA, throttles under load — be polite.

    Availability: https://archive.org/wayback/available?url={url}&timestamp={ts}
    CDX:          https://web.archive.org/cdx/search/cdx?url={url}&output=json
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class WaybackAdapter(CostMixin, RegistryAdapter):
    """Internet Archive historical-snapshot connector (carcass).

    Provides the onboarding-era website content reference; the actual text
    comparison lives in the business-model comparator, not here.
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

    def record_url(self, entity_id: str) -> str | None:
        # entity_id is the domain/URL.
        return f"https://web.archive.org/web/*/{entity_id}"

    async def fetch(
        self, customer_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, customer_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
