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

COST / ACCESS  →  FREE, no API key (PLANNED — implement now)
    Rate-limited (429 during big news events). You MUST send a ``User-Agent``
    header or the API returns nothing.

    Base URL:  https://api.gdeltproject.org/api/v2/doc/doc
    Example:   ?query={name}&mode=artlist&format=json
               ?query={name}&mode=timelinevol&format=json
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class GdeltAdapter(CostMixin, RegistryAdapter):
    """GDELT news-monitoring connector (carcass)."""

    source_name = "gdelt"
    display_name = "GDELT 2.0 (news)"
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    docs_url = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (1, 6, 8, 10)
    signal_types = ("news", "adverse_media", "funding_event")

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
