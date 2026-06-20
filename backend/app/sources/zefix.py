"""
ZEFIX — Swiss Central Business Name Index (Handelsregister).

WHAT IT PROVIDES
    The authoritative register of every company entered in a Swiss cantonal
    commercial register: legal name, UID (CHE-xxx.xxx.xxx), legal form
    (AG/GmbH/SA/Sàrl/...), legal seat (canton/municipality), status (active /
    in liquidation / deleted), and the mutation (last-change) date.

WHY IT MATTERS HERE  (Use cases 4, 7, 8, 10)
    Diffing a current ZEFIX record against the KYC-onboarding baseline catches a
    *secret* legal-name change (Case 8), a legal-form or seat change that shifts
    jurisdiction/regulatory exposure (Case 4), a dissolution/liquidation
    (adverse), and a mutation after a long dormant stretch (Case 7 corroboration).

COST / ACCESS  →  FREE, no API key (PLANNED — implement now)
    Public read API; the name index is published as Swiss Open Data. Fair-use
    rate limiting; a registered account (email zefix@bj.admin.ch) is expected
    only for heavy automated polling.

    Base URL:  https://www.zefix.admin.ch/ZefixPublicREST/
    Endpoints: POST /api/v1/company/search        (by name / UID)
               GET  /api/v1/company/uid/{uid}     (full record)

This is a carcass: ``fetch``/``normalize`` are unimplemented. The field-level
:meth:`RegistryAdapter.diff` already turns a normalized snapshot into signals.
"""

from __future__ import annotations

from app.sources.base import AdapterStatus, EntitySnapshot, RegistryAdapter, SourceCost


class ZefixAdapter(RegistryAdapter):
    """Swiss commercial register connector (carcass)."""

    source_id = "zefix"
    display_name = "ZEFIX (Swiss Commercial Register)"
    base_url = "https://www.zefix.admin.ch/ZefixPublicREST"
    docs_url = "https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html"
    cost = SourceCost.FREE
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (4, 7, 8, 10)
    signal_types = (
        "name_change",
        "legal_form_change",
        "jurisdiction_change",
        "status_change",
        "adverse_media",
    )

    def entity_url(self, entity_id: str) -> str | None:
        # entity_id is the Swiss UID, e.g. "CHE-123.456.789".
        return f"https://www.zefix.admin.ch/en/search/entity/list?name={entity_id}"

    def fetch(self, entity_id: str) -> dict:
        self._carcass()
        raise AssertionError("unreachable")  # pragma: no cover

    def normalize(self, raw: dict) -> EntitySnapshot:
        self._carcass()
        raise AssertionError("unreachable")  # pragma: no cover
