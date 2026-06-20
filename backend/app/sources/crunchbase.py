"""
Crunchbase — funding rounds & company scale events.   *** SKIPPED: PAID ***

WHAT IT WOULD PROVIDE
    Funding-round history (amount, date, investors) and company scale data —
    the canonical feed for Case 6 (large funding round / rapid expansion), where
    a round many multiples above the customer's KYC AUM baseline is the signal,
    and new investors get screened through OpenSanctions.

WHY WE SKIP IT  →  PAID (status = SKIPPED)
    Crunchbase removed free API access in 2025; the API is now enterprise /
    sales-gated (full API behind paid plans). No free path exists, so this
    adapter is intentionally NOT implemented.

    Partial free fallback: a funding/expansion event is usually also *news*, so
    GDELT (free) gives weaker corroboration for Case 6 without the structured
    round amount. We accept the reduced fidelity to stay 100% free.

    Would-be base URL: https://api.crunchbase.com/api/v4/
    ``fetch``/``fetch_signals`` raise :class:`SourceUnavailableError`.
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class CrunchbaseAdapter(CostMixin, RegistryAdapter):
    """Funding-rounds connector — SKIPPED (paid, free tier removed 2025)."""

    source_name = "crunchbase"
    display_name = "Crunchbase (funding)"
    base_url = "https://api.crunchbase.com/api/v4"
    docs_url = "https://data.crunchbase.com/docs"
    cost = SourceCost.PAID
    status = AdapterStatus.SKIPPED
    requires_api_key = True
    use_cases = (6,)
    signal_types = ("funding_event", "ownership_change")

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()  # raises SourceUnavailableError (paid/skipped)

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()  # raises SourceUnavailableError (paid/skipped)
