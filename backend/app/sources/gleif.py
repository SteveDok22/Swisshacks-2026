"""
GLEIF — Global Legal Entity Identifier Foundation.

WHAT IT PROVIDES
    The global LEI reference data set (CC0 open data): per-LEI legal name,
    registration status (ISSUED / LAPSED / RETIRED / ANNULLED), legal
    jurisdiction, headquarters/legal address, and — crucially — the
    relationship graph: ``ultimate-parent`` and ``direct-children`` LEIs.
    The closest thing to a free, global, machine-readable ownership tree.

WHY IT MATTERS HERE  (Use cases 3, 4, 5, 8, 10)
    Diffing resolves: a legal-name change confirmed across borders (Case 8), a
    jurisdiction change (Case 4), an entity going ANNULLED (strong adverse), and
    — via the parent/children endpoints — a changed ultimate parent or a new
    subsidiary, i.e. real UBO/ownership drift (Cases 3, 5) feeding the contagion
    layer instead of a synthetic graph.

COST / ACCESS  →  FREE, no API key  (status: IMPLEMENTED)
    Fully open JSON:API. Max 200 records/request; fair-use rate limiting (429).

    Base URL:  https://api.gleif.org/api/v1/
    Endpoints: GET /lei-records/{lei}
               GET /lei-records/{lei}/ultimate-parent
               GET /lei-records/{lei}/direct-children
               GET /lei-records?filter[entity.legalName]=...   (reverse lookup)

SIGNAL FLOW
    This is a *registry diff* adapter. ``fetch()`` returns the current
    ``EntitySnapshot``; the service layer compares it to the stored KYC baseline
    via ``diff_snapshots(baseline, current)`` and converts ``SnapshotDiff``
    objects to ``PublicSignal`` instances. ``fetch_signals()`` therefore returns
    an empty list — signals are not generated directly by this adapter.

OWNERSHIP REPRESENTATION
    beneficial_owners — list containing the ultimate-parent LEI (entity-level
                        UBO proxy; individual-person resolution requires a paid
                        source such as OpenCorporates)
    officers          — list of direct-child LEIs (subsidiary nodes for the
                        ownership-contagion PageRank layer; stored here because
                        no ``subsidiaries`` field exists on EntitySnapshot)

PAGINATION NOTE
    ``_get_children_leis`` fetches only the first page of direct children
    (GLEIF default page[size]=10). Large holding companies may have more;
    the full ownership graph is truncated.  TODO: paginate direct-children.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

_BASE_URL = "https://api.gleif.org/api/v1"

# GLEIF registration status → internal dissolution_status vocabulary.
# "LAPSED" means the LEI registration expired but the entity's legal existence
# is unconfirmed — NOT the same as "active". We store it as "lapsed" so the
# diff layer can detect ISSUED→LAPSED transitions (a potential KYC signal)
# rather than silently treating both as identical "active" states.
# "PENDING_*" registrations are also in-flight; status unknown → None.
_REG_STATUS_MAP: dict[str, str | None] = {
    "ISSUED": "active",
    "LAPSED": "lapsed",             # renewal expired — entity status unconfirmed
    "PENDING_VALIDATION": None,     # in-flight — true status unknown
    "PENDING_TRANSFER": None,
    "PENDING_ARCHIVAL": "dissolved",
    "RETIRED": "dissolved",
    "ANNULLED": "dissolved",
    "DUPLICATE": "dissolved",
    "TRANSFERRED": "dissolved",
    "MERGED": "dissolved",
}


class GleifAdapter(CostMixin, RegistryAdapter):
    """Global LEI connector — calls api.gleif.org/api/v1 (no key required)."""

    source_name = "gleif"
    display_name = "GLEIF (Global LEI)"
    base_url = _BASE_URL
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
    )

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        # Accept an injected client so tests can pass a mock without any
        # network activity. Track ownership so aclose() only closes clients
        # we created — never ones the caller manages externally.
        if http_client is not None:
            self._http = http_client
            self._owns_client = False
        else:
            self._http = httpx.AsyncClient(
                base_url=_BASE_URL,
                headers={"Accept": "application/vnd.api+json"},
                timeout=10.0,
            )
            self._owns_client = True

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this adapter owns it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> "GleifAdapter":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def record_url(self, entity_id: str) -> str | None:
        # entity_id is the 20-char LEI code.
        return f"https://search.gleif.org/#/record/{entity_id}"

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        """
        Fetch the current GLEIF record for the entity.

        Parameters
        ----------
        drift_id:   internal drift engine ID for the customer.
        name:       legal name used for reverse lookup when ``lei`` is absent.
        lei:        (kwarg) the 20-char LEI code — preferred over name lookup.

        Returns None if the entity is not found in GLEIF, the API is
        unreachable, or rate-limited (429 — caller decides on retry).
        """
        lei: str | None = kwargs.get("lei")
        if not lei:
            lei = await self._lookup_lei_by_name(name)
        if not lei:
            return None

        raw = await self._get_lei_record(lei)
        if raw is None:
            return None

        # Fetch parent and children in parallel — both are optional; failures
        # are swallowed inside the helper methods.
        parent_lei, children_leis = await asyncio.gather(
            self._get_parent_lei(lei),
            self._get_children_leis(lei),
        )

        return self._normalize(drift_id, lei, raw, parent_lei, children_leis)

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        """
        GLEIF is a registry diff adapter; signals are generated by the service
        layer via ``diff_snapshots(baseline, current)`` after calling
        ``fetch()``. Returns empty list to satisfy the abstract contract.
        """
        return []

    # ------------------------------------------------------------------
    # HTTP helpers — all use the ``is_success`` guard so that any non-2xx
    # response (404, 429, 500, 503, …) is swallowed and returns None/[].
    # A transient GLEIF outage must not propagate as an unhandled exception
    # through the drift service.
    # ------------------------------------------------------------------

    async def _get_lei_record(self, lei: str) -> dict[str, Any] | None:
        try:
            resp = await self._http.get(f"/lei-records/{lei}")
        except httpx.TransportError:
            return None
        if not resp.is_success:
            return None
        return resp.json()  # type: ignore[no-any-return]

    async def _lookup_lei_by_name(self, name: str) -> str | None:
        try:
            resp = await self._http.get(
                "/lei-records",
                params={"filter[entity.legalName]": name, "page[size]": "1"},
            )
        except httpx.TransportError:
            return None
        if not resp.is_success:
            return None
        items = resp.json().get("data", [])
        if not items:
            return None
        # Prefer the top-level JSON:API `id` field; fall back to attributes.lei.
        return items[0].get("id") or items[0].get("attributes", {}).get("lei")  # type: ignore[no-any-return]

    async def _get_parent_lei(self, lei: str) -> str | None:
        try:
            resp = await self._http.get(f"/lei-records/{lei}/ultimate-parent")
        except httpx.TransportError:
            return None
        if not resp.is_success:
            return None
        data = resp.json().get("data")
        if not data:
            return None
        return data.get("id") or data.get("attributes", {}).get("lei")  # type: ignore[no-any-return]

    async def _get_children_leis(self, lei: str) -> list[str]:
        try:
            resp = await self._http.get(f"/lei-records/{lei}/direct-children")
        except httpx.TransportError:
            return []
        if not resp.is_success:
            return []
        items = resp.json().get("data", [])
        return [
            item.get("id") or item.get("attributes", {}).get("lei")
            for item in items
            if item.get("id") or item.get("attributes", {}).get("lei")
        ]

    # ------------------------------------------------------------------
    # Normalisation — pure, no I/O
    # ------------------------------------------------------------------

    def _normalize(
        self,
        drift_id: str,
        lei: str,
        raw: dict[str, Any],
        parent_lei: str | None,
        children_leis: list[str],
    ) -> EntitySnapshot:
        data = raw.get("data", {})
        attrs = data.get("attributes", {})
        entity = attrs.get("entity", {})
        registration = attrs.get("registration", {})

        return EntitySnapshot(
            drift_id=drift_id,
            name=_extract_name(entity),
            source=self.source_name,
            legal_form=_extract_legal_form(entity),
            jurisdiction=entity.get("jurisdiction") or None,
            registered_address=_extract_address(entity),
            dissolution_status=_extract_status(entity, registration),
            # Ownership nodes: parent LEI as entity-level UBO proxy; direct
            # children stored in ``officers`` (no ``subsidiaries`` field exists
            # on EntitySnapshot) for the ownership-contagion PageRank layer.
            beneficial_owners=[parent_lei] if parent_lei else [],
            officers=children_leis,
            raw_data={
                "lei": lei,
                "registration_status": registration.get("status"),
                "entity_status": entity.get("status"),
            },
        )


# ---------------------------------------------------------------------------
# Pure normalisation helpers — module-level so tests can call them directly.
# ---------------------------------------------------------------------------

def _extract_name(entity: dict[str, Any]) -> str:
    legal_name = entity.get("legalName", {})
    if isinstance(legal_name, dict):
        return legal_name.get("name", "") or ""
    # Older records may return a plain string.
    return str(legal_name) if legal_name else ""


def _extract_legal_form(entity: dict[str, Any]) -> str | None:
    lf = entity.get("legalForm")
    if not lf or not isinstance(lf, dict):
        return None
    return lf.get("id") or lf.get("other") or None


def _extract_address(entity: dict[str, Any]) -> str | None:
    addr = entity.get("legalAddress")
    if not addr or not isinstance(addr, dict):
        return None
    parts: list[str] = []
    lines = addr.get("addressLines")
    if lines:
        parts.append(lines[0])
    if city := addr.get("city"):
        parts.append(city)
    if country := addr.get("country"):
        parts.append(country)
    return ", ".join(parts) if parts else None


def _extract_status(
    entity: dict[str, Any], registration: dict[str, Any]
) -> str | None:
    # Entity-level INACTIVE is definitive — overrides registration status.
    if entity.get("status") == "INACTIVE":
        return "dissolved"
    return _REG_STATUS_MAP.get(registration.get("status", ""))
