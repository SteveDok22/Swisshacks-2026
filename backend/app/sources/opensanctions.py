"""
OpenSanctions — consolidated sanctions / PEP / watchlist screening.

WHAT IT PROVIDES
    A consolidated, de-duplicated database of OFAC SDN, EU, UN, UK (and many
    more) sanctions lists, plus PEPs and crime/adverse-entity datasets, with a
    built-in name-matching engine that returns a match *score* per candidate.
    Screening is entity-centric (Company / Person / Organization schemas).

WHY IT MATTERS HERE  (Use cases 2, 5)
    Not a field-diff source — a *screening* source. Given a customer name (or a
    UBO/owner pulled from GLEIF), it answers "is this entity, or anyone in its
    ownership chain, on a watchlist?" A high-score hit is a near-certain
    escalation trigger; a UBO hit drives the ``ownership_change`` signal.

    Because it screens rather than diffs, the concrete adapter overrides
    :meth:`RegistryAdapter.diff` (or adds a ``screen(name)`` method) instead of
    using the generic field comparison.

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

from app.sources.base import AdapterStatus, EntitySnapshot, RawRecord, RegistryAdapter, SourceCost


class OpenSanctionsAdapter(RegistryAdapter):
    """Sanctions / PEP screening connector (carcass).

    NOTE: this source *screens* a name rather than diffing two snapshots, so the
    real implementation will override ``diff`` and expose a ``screen`` entry
    point. The metadata and free/paid classification still apply.
    """

    source_id = "opensanctions"
    display_name = "OpenSanctions (OFAC / EU / UN)"
    base_url = "https://api.opensanctions.org"
    docs_url = "https://www.opensanctions.org/docs/api/"
    cost = SourceCost.FREEMIUM
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (2, 5)
    signal_types = ("sanctions", "ownership_change", "adverse_media")

    def entity_url(self, entity_id: str) -> str | None:
        return f"https://www.opensanctions.org/entities/{entity_id}/"

    def fetch(self, entity_id: str) -> RawRecord:
        return self._carcass()

    def normalize(self, raw: RawRecord) -> EntitySnapshot:
        return self._carcass()
