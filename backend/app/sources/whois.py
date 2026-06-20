"""
WHOIS / RDAP — domain registration metadata.

WHAT IT PROVIDES
    Registration data for a customer's domain via RDAP (the structured, JSON
    successor to WHOIS that ICANN mandated as WHOIS sunset on 2025-01-28):
    creation/registration date, last-changed date, registrar, and registrant
    contact (where not redacted).

WHY IT MATTERS HERE  (Use cases 8, 9)
    Two cheap, high-signal checks: (1) domain AGE — a company "established 2009"
    whose domain was registered 3 weeks ago is a red flag (``domain_change``,
    severity scales inversely with age); (2) registrant CHANGE versus the KYC
    baseline — a quiet ownership/control handover that no registry filing shows.

COST / ACCESS  →  FREE, no API key (PLANNED — implement now)
    RDAP is open. The rdap.org aggregator redirects to the authoritative server
    but rate-limits (~10 req / 10 s); for volume, read the IANA bootstrap
    (https://data.iana.org/rdap/dns.json) and query TLD servers directly.

    Base URL:  https://rdap.org/
    Endpoint:  GET /domain/{domain}
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class WhoisAdapter(CostMixin, RegistryAdapter):
    """RDAP/WHOIS domain-registration connector (carcass)."""

    source_name = "whois"
    display_name = "WHOIS / RDAP (domain)"
    base_url = "https://rdap.org"
    docs_url = "https://about.rdap.org/"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (8, 9)
    signal_types = ("domain_change",)

    def record_url(self, entity_id: str) -> str | None:
        return f"https://rdap.org/domain/{entity_id}"

    async def fetch(
        self, customer_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, customer_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
