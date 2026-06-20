"""
ZEFIX — Swiss Central Business Name Index (Handelsregister).

WHAT IT PROVIDES
    The authoritative register of every company entered in a Swiss cantonal
    commercial register: legal name, UID (CHE-xxx.xxx.xxx), legal form
    (AG/GmbH/SA/Sàrl/...), legal seat (municipality) and canton, status
    (ACTIVE / BEING_CANCELLED / CANCELLED), the business purpose (Zweck) and
    the dated SHAB/SOGC publication log (the mutation history).

WHY IT MATTERS HERE  (Use cases 4, 7, 8, 10)
    Fetching a current ZEFIX snapshot and diffing it (``base.diff_snapshots``)
    against the KYC-onboarding baseline catches a *secret* legal-name change
    (Case 8), a legal-form or canton change that shifts the regulatory seat
    (Case 4), a dissolution (adverse), and a mutation after a long dormant
    stretch (Case 7 corroboration). ``purpose`` (Zweck) feeds Case 10.

    NOT available: officers / board members / beneficial owners are NOT in the
    ZefixPublicREST API (they live in the cantonal registers). Case 5
    (new shareholders/UBOs) therefore stays GLEIF's job, not ZEFIX's; this
    adapter always returns empty ``beneficial_owners`` / ``officers``.

API CONTRACT  (verified live against the public OpenAPI spec, 2026-06)
    Base URL:  https://www.zefix.admin.ch/ZefixPublicREST   (HTTP Basic auth)
    POST /api/v1/company/search   body CompanySearchQuery  -> CompanyShort[]
    GET  /api/v1/company/uid/{uid}                          -> CompanyFull[]
    ``legalForm`` is a nested object whose ``shortName``/``name`` are
    DFIEString language maps ({de,fr,it,en}); ``status`` is one of
    ACTIVE / BEING_CANCELLED / CANCELLED. (The ROADMAP pseudocode predates the
    live schema check — there is no ``maxEntries``/``languageKey`` on search,
    and ``legalForm`` is an object, not a string.)

COST / ACCESS  →  FREEMIUM: free, but a (free) registered account is required.
    The ZefixPublicREST API returns ``401 WWW-Authenticate: Basic`` without
    credentials (verified live). Access is HTTP Basic auth with a free account
    requested from the Federal Office of Justice (zefix@bj.admin.ch). No
    payment, fair-use limits. Without credentials this adapter degrades
    gracefully: ``fetch`` returns ``None`` and ``fetch_signals`` returns ``[]``
    so the engine keeps running.

This adapter does NOT touch the database. ``fetch_signals`` diffs the current
snapshot against a *baseline* ``EntitySnapshot`` that the caller injects
(loaded from ``db.kyc_baseline.load_onboarding_snapshot`` by the future
aggregator). Keeping the DB lookup out of the adapter preserves the
``sources`` dependency rule and makes the adapter unit-testable without an ORM.
"""

from __future__ import annotations

import asyncio
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.sources.base import (
    EntitySnapshot,
    PublicSignal,
    RegistryAdapter,
    diff_snapshots,
)
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

logger = get_logger(__name__)

_USER_AGENT = "Sentinel/1.0"

# Human-readable provenance stamped on every PublicSignal this adapter emits.
_SIGNAL_SOURCE = "ZEFIX"

# Minimum name-similarity (difflib ratio) for a search hit to count as a match.
# Below this we treat the entity as "not in this register" and return None.
_MATCH_THRESHOLD = 0.60

# ZEFIX status string -> EntitySnapshot.dissolution_status vocabulary
# ("active" | "dissolved" | "dormant" | "struck_off"). ZEFIX has no "dormant"
# state — dormancy is inferred from transaction silence, not the register.
_STATUS_MAP: dict[str, str] = {
    "ACTIVE": "active",
    "BEING_CANCELLED": "dissolved",   # in liquidation / being struck
    "CANCELLED": "struck_off",        # deleted from the register
}

# Map the past-tense routing keys produced by ``diff_snapshots`` to the
# noun-form ``PublicSignal.signal_type`` vocabulary (see cost.ADAPTER_SIGNAL_TYPES).
# Only the fields ZEFIX is authoritative for are forwarded; an address move
# (low signal, municipality-level) is intentionally dropped.
_DIFF_TO_SIGNAL: dict[str, str] = {
    "name_changed": "name_change",
    "legal_form_changed": "legal_form_change",
    "jurisdiction_changed": "jurisdiction_change",
    "dissolution_status_changed": "status_change",
}

# Terminal statuses that are adverse on their own, with no baseline to diff.
_TERMINAL_STATUSES = ("dissolved", "struck_off")
_TERMINAL_SEVERITY = 0.90


def _dfie(value: Any, *, prefer: tuple[str, ...] = ("de", "en", "fr", "it")) -> str | None:
    """Read a DFIEString language map, returning the first non-empty language.

    Swiss legal-form abbreviations (AG/GmbH) are German, so ``de`` is preferred
    first for those; callers can override the order.
    """
    if not isinstance(value, dict):
        return value if isinstance(value, str) and value else None
    for lang in prefer:
        text = value.get(lang)
        if text:
            return text
    # Fall back to any populated language.
    for text in value.values():
        if text:
            return text
    return None


def _best_match(name: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the candidate whose ``name`` is most similar to ``name``.

    Uses difflib's ratio (a Levenshtein-equivalent for short strings, no extra
    dependency). Returns ``None`` when the best score is below the threshold so
    a weak/garbage hit is treated as "not registered here".
    """
    target = name.strip().lower()
    best: dict[str, Any] | None = None
    best_score = 0.0
    for cand in candidates:
        if not isinstance(cand, dict):
            continue  # malformed payload element → treat as no candidate
        cand_name = (cand.get("name") or "").strip().lower()
        if not cand_name:
            continue
        score = SequenceMatcher(None, target, cand_name).ratio()
        if score > best_score:
            best, best_score = cand, score
    return best if best_score >= _MATCH_THRESHOLD else None


def _format_address(addr: dict[str, Any] | None, legal_seat: str | None) -> str | None:
    """Build a one-line registered address from a ZEFIX Address object."""
    if not isinstance(addr, dict):
        return legal_seat or None
    # ZEFIX may serialise swissZipCode / houseNumber as ints — coerce to str so
    # str.join doesn't TypeError on live data (string fixtures hide this).
    street = " ".join(str(p) for p in (addr.get("street"), addr.get("houseNumber")) if p)
    locality = " ".join(str(p) for p in (addr.get("swissZipCode"), addr.get("city")) if p)
    line = ", ".join(p for p in (street, locality) if p)
    return line or legal_seat or None


class ZefixAdapter(CostMixin, RegistryAdapter):
    """Swiss commercial register connector (ZefixPublicREST)."""

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
    # Only the change types this adapter actually emits (diff-derived plus the
    # terminal-status path). SHAB-derived adverse_media is a future addition.
    signal_types = (
        "name_change",
        "legal_form_change",
        "jurisdiction_change",
        "status_change",
    )

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ) -> None:
        # Fall back to configured credentials when not explicitly injected.
        self._username = settings.zefix_username if username is None else username
        self._password = settings.zefix_password if password is None else password
        # An injected client (tests / shared pool) is reused and never closed by
        # this adapter; otherwise a short-lived client is created per fetch().
        self._client = client
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._backoff_base = backoff_base

    @property
    def _has_credentials(self) -> bool:
        return bool(self._username and self._password)

    def record_url(self, entity_id: str) -> str | None:
        # entity_id is the Swiss UID, e.g. "CHE-123.456.789".
        return f"https://www.zefix.admin.ch/en/search/entity/list?name={entity_id}"

    # ------------------------------------------------------------------ #
    # HTTP plumbing                                                        #
    # ------------------------------------------------------------------ #
    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=httpx.BasicAuth(self._username, self._password),
            headers={"User-Agent": _USER_AGENT},
            timeout=self._timeout,
        )

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        json: Any | None = None,
    ) -> Any:
        """Send one request, retrying on 429/503 with exponential backoff.

        Returns the parsed JSON body. Raises ``httpx.HTTPStatusError`` for a
        non-retryable error status (per the RegistryAdapter contract: only
        absence of data is silent; network/HTTP errors propagate).
        """
        last = self._max_retries - 1
        for attempt in range(self._max_retries):
            response = await client.request(method, url, json=json)
            if response.status_code in (429, 503) and attempt < last:
                await asyncio.sleep(self._backoff_base * (2**attempt))
                continue
            response.raise_for_status()
            return response.json()
        # Unreachable: the final attempt either returns or raises above.
        raise RuntimeError("retry loop exhausted without a response")  # pragma: no cover

    # ------------------------------------------------------------------ #
    # Snapshot mapping                                                     #
    # ------------------------------------------------------------------ #
    def _to_snapshot(self, drift_id: str, full: dict[str, Any]) -> EntitySnapshot:
        """Map a ZEFIX CompanyFull record onto a canonical EntitySnapshot.

        ``jurisdiction`` carries the Swiss canton (e.g. "ZG"): for a
        single-country register the operative jurisdictional change for Case 4
        is the cantonal seat, not the country (invariantly CH, kept in
        ``raw_data``). The municipality lands in ``registered_address``.
        """
        legal_form_obj = full.get("legalForm") or {}
        legal_form = _dfie(legal_form_obj.get("shortName"))
        status_raw = full.get("status")
        dissolution_status = _STATUS_MAP.get(status_raw) if status_raw else None
        if status_raw and dissolution_status is None:
            # A new/unknown ZEFIX status would otherwise vanish silently and
            # could even fire a spurious diff (value → None). Surface it.
            logger.warning("zefix_unmapped_status", drift_id=drift_id, status=status_raw)
        legal_seat = full.get("legalSeat")
        canton = full.get("canton")

        sogc_pubs = full.get("sogcPub") or []
        first_pub = sogc_pubs[0] if sogc_pubs and isinstance(sogc_pubs[0], dict) else None
        mutation_date = first_pub.get("sogcDate") if first_pub else full.get("sogcDate")
        old_names = [
            n["name"]
            for n in (full.get("oldNames") or [])
            if isinstance(n, dict) and n.get("name")
        ]

        return EntitySnapshot(
            drift_id=drift_id,
            name=full.get("name") or "",
            source=self.source_name,
            legal_form=legal_form,
            jurisdiction=canton,
            registered_address=_format_address(full.get("address"), legal_seat),
            dissolution_status=dissolution_status,
            # ZEFIX exposes no officers / UBOs — left empty by design.
            beneficial_owners=[],
            officers=[],
            raw_data={
                "uid": full.get("uid"),
                "ehraid": full.get("ehraid"),
                "chid": full.get("chid"),
                "country": "CH",
                "canton": canton,
                "legal_seat": legal_seat,
                "status_raw": status_raw,
                "legal_form": legal_form_obj,
                "purpose": full.get("purpose"),
                "mutation_date": mutation_date,
                "old_names": old_names,
                "capital_nominal": full.get("capitalNominal"),
                "capital_currency": full.get("capitalCurrency"),
                "deletion_date": full.get("deletionDate"),
            },
        )

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    async def fetch(
        self, drift_id: str, name: str, *, uid: str | None = None, **kwargs: Any
    ) -> EntitySnapshot | None:
        """Fetch the current ZEFIX snapshot for ``name``.

        When ``uid`` (a Swiss company UID, e.g. "CHE-123.456.789") is supplied
        the fuzzy name search is skipped and the record is fetched directly —
        the reliable path the RegistryAdapter contract advertises. Returns
        ``None`` when no account is configured (graceful degradation) or when
        the entity is not found in the register.
        """
        if not self._has_credentials:
            logger.warning(
                "zefix_no_credentials",
                drift_id=drift_id,
                detail="ZEFIX account not configured; skipping fetch",
            )
            return None

        client = self._client or self._new_client()
        owns_client = self._client is None
        try:
            if not uid:  # None or "" → resolve via name search
                candidates = await self._send(
                    client,
                    "POST",
                    "/api/v1/company/search",
                    json={"name": name, "activeOnly": False},
                )
                if not isinstance(candidates, list):
                    return None
                best = _best_match(name, candidates)
                if best is None or not best.get("uid"):
                    logger.info("zefix_no_match", drift_id=drift_id, name=name)
                    return None
                uid = best["uid"]

            records = await self._send(
                client, "GET", f"/api/v1/company/uid/{uid}"
            )
            if not isinstance(records, list) or not records:
                return None
            # A UID can return several records (head office + branches); pick the
            # one whose name best matches the query, falling back to the first.
            full = _best_match(name, records) or records[0]
            return self._to_snapshot(drift_id, full)
        finally:
            if owns_client:
                await client.aclose()

    async def fetch_signals(
        self,
        drift_id: str,
        name: str,
        since_month: int = 0,
        *,
        baseline: EntitySnapshot | None = None,
        current: EntitySnapshot | None = None,
        **kwargs: Any,
    ) -> list[PublicSignal]:
        """Return ZEFIX change signals for the entity.

        With a ``baseline`` (the KYC onboarding snapshot, injected by the
        caller) the current snapshot is diffed field-by-field and each relevant
        change becomes a ``PublicSignal``. Without a baseline only an absolute
        adverse status (dissolution / strike-off) is reported.

        ``month`` is set to ``since_month`` — the as-of scan month. Aligning a
        registry mutation date to the engine's month index is the aggregator's
        responsibility, not the adapter's.

        CONTRACT: the injected ``baseline`` MUST be a same-source ZEFIX snapshot.
        ``jurisdiction`` carries the Swiss *canton* (not an ISO country code), so
        diffing against a baseline captured by another source that stored a
        country code ("CH") would emit a spurious ``jurisdiction_change``. The
        aggregator owns this guarantee (it loads the onboarding ZEFIX snapshot).
        """
        # Diffing two caller-supplied snapshots is pure compute — no account
        # needed. Only the network fetch path requires credentials.
        snapshot = current
        if snapshot is None:
            if not self._has_credentials:
                return []
            snapshot = await self.fetch(drift_id, name, **kwargs)
        if snapshot is None:
            return []

        uid = snapshot.raw_data.get("uid")
        source_url = self.record_url(uid) if uid else None
        signals: list[PublicSignal] = []

        # Enforce the same-source contract at runtime: ``jurisdiction`` holds a
        # canton (not an ISO country) and name/legal-form formatting differs per
        # source, so a cross-source diff would emit spurious signals. A mismatched
        # baseline is treated as "no usable baseline" — the diff is skipped, but
        # an absolute adverse status below still fires.
        usable_baseline = baseline
        if baseline is not None and baseline.source != snapshot.source:
            logger.warning(
                "zefix_baseline_source_mismatch",
                drift_id=drift_id,
                baseline_source=baseline.source,
                current_source=snapshot.source,
            )
            usable_baseline = None

        if usable_baseline is not None:
            for change in diff_snapshots(usable_baseline, snapshot):
                signal_type = _DIFF_TO_SIGNAL.get(change.drift_signal_type)
                if signal_type is None:
                    continue
                signals.append(
                    PublicSignal(
                        month=since_month,
                        signal_type=signal_type,
                        headline=self._headline(signal_type, change.old_value, change.new_value),
                        severity=change.severity,
                        source=_SIGNAL_SOURCE,
                        source_url=source_url,
                    )
                )
        elif snapshot.dissolution_status in _TERMINAL_STATUSES:
            # No baseline to diff against, but a current terminal status is
            # adverse on its own.
            signals.append(
                PublicSignal(
                    month=since_month,
                    signal_type="status_change",
                    headline=f"Registration status: {snapshot.dissolution_status}",
                    severity=_TERMINAL_SEVERITY,
                    source=_SIGNAL_SOURCE,
                    source_url=source_url,
                )
            )

        return signals

    @staticmethod
    def _headline(signal_type: str, old: Any, new: Any) -> str:
        labels = {
            "name_change": "Legal name changed",
            "legal_form_change": "Legal form changed",
            "jurisdiction_change": "Legal seat (canton) changed",
            "status_change": "Registration status changed",
        }
        label = labels.get(signal_type, signal_type)
        return f"{label}: {old!r} → {new!r}"
