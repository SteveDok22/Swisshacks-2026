"""
OpenCorporates — company / officers / directors data.   *** SKIPPED: PAID ***

WHAT IT WOULD PROVIDE
    The largest open database of companies worldwide: registration data plus
    directors/officers and (some) corporate relationships across jurisdictions
    where GLEIF has no LEI coverage — useful for officer-level UBO resolution.

WHY WE SKIP IT  →  PAID / approval-gated (status = SKIPPED)
    There is no usable free tier for a normal demo. Free API keys are granted
    only to genuine open-data projects that agree to republish their output
    under an open licence with attribution; general/commercial use starts at a
    self-serve plan on the order of £2,250/yr. That fails the "100% free, usable
    now" bar, so this adapter is intentionally NOT implemented.

    Coverage overlap: GLEIF (free) covers ownership/parent-child for LEI'd
    entities (Cases 3, 4, 5); ZEFIX (free) covers Swiss officers. OpenCorporates
    would only add officer breadth in non-LEI jurisdictions — not worth the cost
    for the MVP.

    Would-be base URL: https://api.opencorporates.com/v0.4/
    ``fetch`` raises :class:`SourceUnavailableError` via ``_carcass``.
"""

from __future__ import annotations

from app.sources.base import AdapterStatus, EntitySnapshot, RegistryAdapter, SourceCost


class OpenCorporatesAdapter(RegistryAdapter):
    """Officers/directors connector — SKIPPED (paid, no usable free tier)."""

    source_id = "open_corporates"
    display_name = "OpenCorporates (officers)"
    base_url = "https://api.opencorporates.com/v0.4"
    docs_url = "https://api.opencorporates.com/documentation/API-Reference"
    cost = SourceCost.PAID
    status = AdapterStatus.SKIPPED
    requires_api_key = True
    use_cases = (3, 4, 5, 7)
    signal_types = ("ownership_change", "name_change", "jurisdiction_change")

    def fetch(self, entity_id: str) -> dict:
        self._carcass()  # raises SourceUnavailableError (paid/skipped)
        raise AssertionError("unreachable")  # pragma: no cover

    def normalize(self, raw: dict) -> EntitySnapshot:
        self._carcass()
        raise AssertionError("unreachable")  # pragma: no cover
