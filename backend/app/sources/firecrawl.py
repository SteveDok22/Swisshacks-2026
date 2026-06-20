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

COST / ACCESS  →  FREEMIUM, API key for cloud (PLANNED — implement now)
    Cloud free tier: ~1,000 credits/month (1 credit/page), no card required —
    enough for a hackathon. Self-hostable (AGPL-3.0) for free but operationally
    heavy (headless browsers, proxies). AGPL matters if you redistribute.

    Base URL:  https://api.firecrawl.dev/v1/
    Endpoints: POST /scrape  (-> markdown)   POST /crawl   POST /map
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class FirecrawlAdapter(CostMixin, RegistryAdapter):
    """Live website-content scraper (carcass).

    Supplies page content rather than canonical registry fields; the real diff
    is embedding-distance in the business-model comparator.
    """

    source_name = "firecrawl"
    display_name = "Firecrawl (website scrape)"
    base_url = "https://api.firecrawl.dev/v1"
    docs_url = "https://docs.firecrawl.dev/"
    cost = SourceCost.FREEMIUM
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (9, 10)
    signal_types = ("business_model_change",)

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
