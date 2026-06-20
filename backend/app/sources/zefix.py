"""
ZEFIX — Swiss Central Business Name Index (Handelsregister).

WHAT IT PROVIDES
    The authoritative register of every company entered in a Swiss cantonal
    commercial register: legal name, UID (CHE-xxx.xxx.xxx), legal form
    (AG/GmbH/SA/Sàrl/...), legal seat (canton/municipality), status (active /
    in liquidation / deleted), and the mutation (last-change) date.

WHY IT MATTERS HERE  (Use cases 4, 7, 8, 10)
    Fetching a current ZEFIX snapshot and diffing it (``base.diff_snapshots``)
    against the KYC-onboarding baseline catches a *secret* legal-name change
    (Case 8), a legal-form or seat change that shifts jurisdiction/regulatory
    exposure (Case 4), a dissolution (adverse), and a mutation after a long
    dormant stretch (Case 7 corroboration). The detail record also carries
    ``purpose`` (Zweck — business-activity text → Case 10 corroboration) and
    SHAB/SOGC publications (a dated mutation log → change *timing*).

    NOT available: officers / board members / beneficial owners are NOT in the
    ZEFIX PublicREST API (they live in the cantonal registers). Case 5
    (new shareholders/UBOs) therefore stays GLEIF's job, not ZEFIX's.

COST / ACCESS  →  FREEMIUM: free, but a (free) registered account is required.
    Verified live (2026-06): the ZefixPublicREST API returns
    ``401 WWW-Authenticate: Basic realm="ZefixPublicREST"`` without credentials.
    Access is HTTP Basic auth with a free account requested from the Federal
    Office of Justice (email zefix@bj.admin.ch). No payment, fair-use limits.
    (The daily ZEFIX *Open Data* bulk dump is the only no-auth path, but it is a
    snapshot of the name index, not live per-entity detail.)

    Base URL:  https://www.zefix.admin.ch/ZefixPublicREST/   (HTTP Basic auth)
    Endpoints: POST /api/v1/company/search        (by name / UID)
               GET  /api/v1/company/uid/{uid}     (records for a UID)
               GET  /api/v1/firm/{ehraid}         (full detail + purpose + SHAB)

Carcass: ``fetch``/``fetch_signals`` are unimplemented (raise via ``_carcass``).
"""

from __future__ import annotations

from typing import Any

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost


class ZefixAdapter(CostMixin, RegistryAdapter):
    """Swiss commercial register connector (carcass)."""

    source_name = "zefix"
    display_name = "ZEFIX (Swiss Commercial Register)"
    base_url = "https://www.zefix.admin.ch/ZefixPublicREST"
    docs_url = "https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html"
    # FREEMIUM, not FREE: the REST API needs a free registered Basic-auth
    # account (verified live — 401 without credentials). No payment involved.
    cost = SourceCost.FREEMIUM
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (4, 7, 8, 10)
    signal_types = (
        "name_change",
        "legal_form_change",
        "jurisdiction_change",
        "status_change",
        "adverse_media",
    )

    def record_url(self, entity_id: str) -> str | None:
        # entity_id is the Swiss UID, e.g. "CHE-123.456.789".
        return f"https://www.zefix.admin.ch/en/search/entity/list?name={entity_id}"

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        return self._carcass()

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        return self._carcass()
