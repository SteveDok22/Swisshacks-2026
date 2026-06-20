"""
WHOIS / RDAP - domain registration metadata.

WHAT IT PROVIDES
    Registration data for a customer's domain via RDAP (the structured, JSON
    successor to WHOIS that ICANN mandated as WHOIS sunset on 2025-01-28):
    creation/registration date, last-changed date, registrar, and registrant
    contact (where not redacted).

WHY IT MATTERS HERE  (Use cases 8, 9)
    Two cheap, high-signal checks: (1) domain AGE - a company "established 2009"
    whose domain was registered 3 weeks ago is a red flag (``domain_change``,
    severity scales inversely with age); (2) registrant CHANGE versus the KYC
    baseline - a quiet ownership/control handover that no registry filing shows.

COST / ACCESS  ->  FREE, no API key
    RDAP is open. The rdap.org aggregator redirects to the authoritative server
    but rate-limits (~10 req / 10 s); for volume, read the IANA bootstrap
    (https://data.iana.org/rdap/dns.json) and query TLD servers directly.

    Base URL:  https://rdap.org/
    Endpoint:  GET /domain/{domain}

This adapter does NOT touch the database. ``fetch_signals`` diffs the current
RDAP snapshot against a *baseline* ``EntitySnapshot`` that the caller injects
(loaded from ``db.kyc_baseline.load_onboarding_snapshot`` by the future
aggregator). Keeping the DB lookup out of the adapter preserves the
``sources`` dependency rule and makes the adapter unit-testable without an ORM.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

_BASE_URL = "https://rdap.org"
_SIGNAL_SOURCE = "RDAP / WHOIS"
_USER_AGENT = "Sentinel/1.0"

_DOMAIN_RE = re.compile(r"^(?:https?://)?(?:www\.)?([^/\s]+)", re.IGNORECASE)
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(ag|sa|gmbh|sarl|sàrl|ltd|limited|inc|corp|corporation|llc|plc|bv|nv)\b",
    re.IGNORECASE,
)

_REGISTRANT_CHANGE_SEVERITY = 0.70
_VERY_YOUNG_DOMAIN_DAYS = 30
_YOUNG_DOMAIN_DAYS = 180
_CLAIMED_ESTABLISHED_DAYS = 365 * 2


class WhoisAdapter(CostMixin, RegistryAdapter):
    """RDAP/WHOIS domain-registration connector (free, no key required)."""

    source_name = "whois"
    display_name = "WHOIS / RDAP (domain)"
    base_url = _BASE_URL
    docs_url = "https://about.rdap.org/"
    cost = SourceCost.FREE
    # PLANNED is the correct value here — the registry invariant is
    # PLANNED↔FREE/FREEMIUM (enforced by tests). This adapter is FULLY
    # IMPLEMENTED: fetch and fetch_signals run live RDAP calls. PLANNED means
    # "usable / not skipped", not "carcass" — AdapterStatus has no LIVE variant.
    status = AdapterStatus.PLANNED
    requires_api_key = False
    use_cases = (8, 9)
    signal_types = ("domain_change", "domain_age")

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        *,
        timeout: float = 10.0,
    ) -> None:
        if http_client is not None:
            self._http = http_client
            self._owns_client = False
        else:
            self._http = httpx.AsyncClient(
                base_url=_BASE_URL,
                headers={
                    "Accept": "application/rdap+json, application/json",
                    "User-Agent": _USER_AGENT,
                },
                timeout=timeout,
                follow_redirects=True,
            )
            self._owns_client = True

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this adapter owns it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> WhoisAdapter:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def record_url(self, entity_id: str) -> str | None:
        domain = _normalize_domain(entity_id)
        return f"{_BASE_URL}/domain/{domain}" if domain else None

    async def fetch(
        self, drift_id: str, name: str, *, domain: str | None = None, **kwargs: Any
    ) -> EntitySnapshot | None:
        """
        Fetch the current RDAP snapshot for ``domain``.

        ``domain`` is the reliable path. If absent, the adapter first looks for
        ``url``/``website`` kwargs and finally falls back to a conservative
        ``{name_slug}.com`` heuristic as documented in the roadmap.
        """
        lookup_domain = _resolve_domain(name, domain=domain, **kwargs)
        if lookup_domain is None:
            return None

        raw = await self._get_domain(lookup_domain)
        if raw is None:
            return None
        return self._normalize(drift_id, name, lookup_domain, raw)

    async def fetch_signals(
        self,
        drift_id: str,
        name: str,
        since_month: int = 0,
        *,
        baseline: EntitySnapshot | None = None,
        current: EntitySnapshot | None = None,
        claimed_company_age_days: int | None = None,
        company_founded_at: date | datetime | str | None = None,
        **kwargs: Any,
    ) -> list[PublicSignal]:
        """
        Return domain-change signals for the entity.

        With a same-source ``baseline`` the RDAP registrant organisation is
        compared against the current snapshot. Domain-age signals are emitted
        only when the caller provides a company-age hint (``claimed_company_age_days``
        or ``company_founded_at``) showing that the company claims to be older
        than two years.
        """
        snapshot = current or await self.fetch(drift_id, name, **kwargs)
        if snapshot is None:
            return []

        source_url = self.record_url(snapshot.raw_data.get("domain", ""))
        signals: list[PublicSignal] = []

        if baseline is not None and baseline.source == snapshot.source:
            old_org = _clean_text(baseline.raw_data.get("registrant_org"))
            new_org = _clean_text(snapshot.raw_data.get("registrant_org"))
            if old_org and new_org and old_org.casefold() != new_org.casefold():
                signals.append(
                    PublicSignal(
                        month=since_month,
                        signal_type="domain_change",
                        headline=f"Domain registrant changed: {old_org!r} -> {new_org!r}",
                        severity=_REGISTRANT_CHANGE_SEVERITY,
                        source=_SIGNAL_SOURCE,
                        source_url=source_url,
                    )
                )

        company_age_days = _company_age_days(
            claimed_company_age_days=claimed_company_age_days,
            company_founded_at=company_founded_at,
        )
        registered_at = _parse_rdap_datetime(snapshot.raw_data.get("registered_at"))
        if (
            registered_at is not None
            and company_age_days is not None
            and company_age_days > _CLAIMED_ESTABLISHED_DAYS
        ):
            age_days = max(0, (datetime.now(UTC) - registered_at).days)
            severity = _domain_age_severity(age_days)
            if severity is not None:
                signals.append(
                    PublicSignal(
                        month=since_month,
                        signal_type="domain_age",
                        headline=(
                            "Domain registered recently vs claimed company age: "
                            f"{age_days} days old"
                        ),
                        severity=severity,
                        source=_SIGNAL_SOURCE,
                        source_url=source_url,
                    )
                )

        return signals

    async def _get_domain(self, domain: str) -> dict[str, Any] | None:
        try:
            resp = await self._http.get(f"/domain/{domain}")
        except httpx.TransportError:
            return None
        if not resp.is_success:
            return None
        try:
            payload = resp.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def _normalize(
        self,
        drift_id: str,
        name: str,
        domain: str,
        raw: dict[str, Any],
    ) -> EntitySnapshot:
        registered_at = _event_date(raw, "registration")
        last_changed = _event_date(raw, "last changed") or _event_date(raw, "last update")
        registrar = _entity_name(raw, "registrar")
        registrant_org = _entity_name(raw, "registrant")

        return EntitySnapshot(
            drift_id=drift_id,
            name=registrant_org or name,
            source=self.source_name,
            raw_data={
                "domain": domain,
                "registered_at": registered_at,
                "last_changed": last_changed,
                "registrar": registrar,
                "registrant_org": registrant_org,
                "status": raw.get("status") if isinstance(raw.get("status"), list) else [],
                "rdap_handle": raw.get("handle"),
            },
        )


def _resolve_domain(
    name: str,
    *,
    domain: str | None = None,
    url: str | None = None,
    website: str | None = None,
    **_: Any,
) -> str | None:
    for val in (domain, url, website):
        if found := _normalize_domain(val):
            return found
    slug = _name_to_domain_slug(name)
    return f"{slug}.com" if slug else None


def _normalize_domain(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    match = _DOMAIN_RE.match(text)
    if not match:
        return None
    domain = match.group(1).split(":")[0].strip(".")
    return domain or None


def _name_to_domain_slug(name: str) -> str | None:
    stripped = _LEGAL_SUFFIX_RE.sub("", name)
    # Preserve hyphens so "Hello-World GmbH" → "hello-world.com", not "helloworld.com"
    slug = re.sub(r"[^a-z0-9-]+", "", stripped.lower()).strip("-")
    return slug or None


def _event_date(raw: dict[str, Any], action: str) -> str | None:
    action_cf = action.casefold()
    for event in raw.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_action = str(event.get("eventAction") or "").casefold()
        if event_action == action_cf:
            return _clean_text(event.get("eventDate"))
    return None


def _entity_name(raw: dict[str, Any], role: str) -> str | None:
    role_cf = role.casefold()
    for entity in raw.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        roles = [str(r).casefold() for r in entity.get("roles") or []]
        if role_cf not in roles:
            continue
        if name := _vcard_value(entity, "org"):
            return name
        if name := _vcard_value(entity, "fn"):
            return name
        if name := _clean_text(entity.get("handle")):
            return name
    return None


def _vcard_value(entity: dict[str, Any], prop_name: str) -> str | None:
    vcard = entity.get("vcardArray")
    if not isinstance(vcard, list) or len(vcard) < 2 or not isinstance(vcard[1], list):
        return None
    for prop in vcard[1]:
        if not isinstance(prop, list) or len(prop) < 4:
            continue
        if str(prop[0]).casefold() != prop_name.casefold():
            continue
        value = prop[3]
        if isinstance(value, list):
            value = " ".join(str(v) for v in value if v)
        return _clean_text(value)
    return None


def _parse_rdap_datetime(value: Any) -> datetime | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text), datetime.min.time(), UTC)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _company_age_days(
    *,
    claimed_company_age_days: int | None = None,
    company_founded_at: date | datetime | str | None = None,
) -> int | None:
    if claimed_company_age_days is not None:
        return claimed_company_age_days if claimed_company_age_days >= 0 else None
    founded_at = _parse_company_date(company_founded_at)
    if founded_at is None:
        return None
    return max(0, (datetime.now(UTC).date() - founded_at).days)


def _parse_company_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        parsed = _parse_rdap_datetime(value)
        return parsed.date() if parsed else None
    return None


def _domain_age_severity(age_days: int) -> float | None:
    if age_days < _VERY_YOUNG_DOMAIN_DAYS:
        return 0.80
    if age_days < _YOUNG_DOMAIN_DAYS:
        return 0.45
    return None


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None
