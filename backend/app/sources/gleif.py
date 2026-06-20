"""
GLEIF — Global Legal Entity Identifier Foundation.

WHAT IT PROVIDES
    The global LEI reference data set (CC0 open data): per-LEI legal name,
    registration status (ISSUED / LAPSED / RETIRED / ANNULLED), legal
    jurisdiction, headquarters/legal address, and — crucially — the
    relationship graph: ``ultimate-parent``, ``direct-parent`` and
    ``direct-children`` LEIs. The closest thing to a free, global,
    machine-readable ownership tree.

WHY IT MATTERS HERE  (Use cases 3, 4, 5, 8, 10)
    Diffing resolves: a legal-name change confirmed across borders (Case 8), a
    jurisdiction change (Case 4), an entity going ANNULLED (strong adverse), and
    — via the parent/children endpoints — a changed ultimate parent or a new
    subsidiary, i.e. real UBO/ownership drift (Cases 3, 5) feeding the contagion
    layer instead of a synthetic graph.

COST / ACCESS  →  FREE, no API key (PLANNED — implement now)
    Fully open JSON:API. Max 200 records/request; fair-use rate limiting (429).

    Base URL:  https://api.gleif.org/api/v1/
    Endpoints: GET /lei-records/{lei}
               GET /lei-records/{lei}/ultimate-parent
               GET /lei-records/{lei}/direct-children
               GET /lei-records?filter[entity.legalName]=...   (reverse lookup)
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class GleifAdapter(CostMixin, RegistryAdapter):
    """Global LEI connector (carcass)."""

    source_name = "gleif"
    display_name = "GLEIF (Global LEI)"
    base_url = "https://api.gleif.org/api/v1"
    docs_url = "https://www.gleif.org/en/lei-data/gleif-api"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (3, 4, 5, 8, 10)
    signal_types = (
        "name_change",
        "jurisdiction_change",
        "status_change",
        "ownership_change",
        "adverse_media",
    )

    def record_url(self, entity_id: str) -> str | None:
        # entity_id is the 20-char LEI.
        return f"https://search.gleif.org/#/record/{entity_id}"

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
