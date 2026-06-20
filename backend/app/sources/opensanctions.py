"""
OpenSanctions — consolidated sanctions / PEP / watchlist screening.

WHAT IT PROVIDES
    A consolidated, de-duplicated database of OFAC SDN, EU, UN, UK (and many
    more) sanctions lists, plus PEPs and crime/adverse-entity datasets, with a
    built-in name-matching engine that returns a match *score* per candidate.

WHY IT MATTERS HERE  (Use cases 2, 5)
    A *screening* source, not a registry-diff source. Given a customer name (or
    a UBO/officer pulled from GLEIF), it answers "is this entity, or anyone in
    its ownership chain, on a watchlist?" A high-score hit is a near-certain
    escalation trigger; a UBO hit drives an ``ownership_change`` signal. The hits
    surface through ``fetch_signals`` (as ``sanctions`` PublicSignals) rather
    than through a snapshot diff.

COST / ACCESS  →  FREEMIUM, API key for hosted (PLANNED — implement now)
    Hosted SaaS API is metered with a small free testing allowance and needs a
    key. The data + the ``yente`` matching service are free for NON-COMMERCIAL
    use and can be self-hosted (Docker: app + Elasticsearch, ~8-16 GB RAM).
    COMMERCIAL use of the data requires a paid bulk-data licence — flag this for
    production. Usable free for a hackathon/non-commercial demo.

    Base URL:  https://api.opensanctions.org/   (or self-hosted yente)
    Endpoints: GET  /search/{dataset}?q={name}&schema=Company
               POST /match/{dataset}            (structured entity matching)
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class OpenSanctionsAdapter(CostMixin, RegistryAdapter):
    """Sanctions / PEP screening connector (carcass).

    Screens a name rather than fetching a registry snapshot: the real ``fetch``
    will return ``None`` (no canonical entity record) and the signal lives in
    ``fetch_signals``.
    """

    source_name = "opensanctions"
    display_name = "OpenSanctions (OFAC / EU / UN)"
    base_url = "https://api.opensanctions.org"
    docs_url = "https://www.opensanctions.org/docs/api/"
    cost = SourceCost.FREEMIUM
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (2, 5)
    signal_types = ("sanctions", "ownership_change", "adverse_media")

    def record_url(self, entity_id: str) -> str | None:
        return f"https://www.opensanctions.org/entities/{entity_id}/"

    async def fetch(
        self, customer_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, customer_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
