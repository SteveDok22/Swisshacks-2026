"""
GDELT 2.0 (DOC 2.0 API) — global news monitoring.  FREE news alternative.

WHAT IT PROVIDES
    Worldwide news article search over a rolling window with article lists
    (``mode=artlist``) and volume time-series (``mode=timelinevol``), filterable
    by entity/keyword, language and tone. No key, no cost.

WHY IT MATTERS HERE  (Use cases 1, 6, 8, 10)
    This is the sustainable, free replacement for the (paid) Event Registry
    adapter. The article/volume time-series per customer feeds BOCPD on the news
    count (Case 1 negative-news spike); article tone seeds the ``news`` /
    ``adverse_media`` severity; coverage of a funding/expansion event corroborates
    Case 6. Because the signal is a time-series, the real adapter overrides
    ``diff`` to run BOCPD rather than field comparison.

COST / ACCESS  →  FREE, no API key (PLANNED — implement now)
    Rate-limited (429 during big news events). You MUST send a ``User-Agent``
    header or the API returns nothing.

    Base URL:  https://api.gdeltproject.org/api/v2/doc/doc
    Example:   ?query={name}&mode=artlist&format=json
               ?query={name}&mode=timelinevol&format=json
"""

from __future__ import annotations

from app.sources.base import AdapterStatus, EntitySnapshot, RegistryAdapter, SourceCost


class GdeltAdapter(RegistryAdapter):
    """GDELT news-monitoring connector (carcass).

    A *news time-series* source, not a field-diff source: the real implementation
    overrides ``diff`` to run BOCPD over the per-month article count and classify
    tone, emitting ``news`` / ``adverse_media`` signals.
    """

    source_id = "gdelt"
    display_name = "GDELT 2.0 (news)"
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    docs_url = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (1, 6, 8, 10)
    signal_types = ("news", "adverse_media", "funding_event")

    def fetch(self, entity_id: str) -> dict:
        self._carcass()
        raise AssertionError("unreachable")  # pragma: no cover

    def normalize(self, raw: dict) -> EntitySnapshot:
        self._carcass()
        raise AssertionError("unreachable")  # pragma: no cover
