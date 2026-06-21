"""
OpenSanctions — consolidated sanctions / PEP / watchlist screening.

WHAT IT PROVIDES
    A consolidated, de-duplicated database of OFAC SDN, EU, UN, UK (and many
    more) sanctions lists, plus PEPs and crime/adverse-entity datasets, with a
    built-in name-matching engine that returns a match *score* per candidate.

WHY IT MATTERS HERE  (Use cases 2, 5)
    A *screening* source, not a registry-diff source. Given a customer name (or
    a UBO/officer pulled from GLEIF), it answers "is this entity, or anyone in
    its ownership chain, on a watchlist?" A high-score hit is a near-certain
    escalation trigger; a UBO hit drives an ``ownership_change`` signal. The hits
    surface through ``fetch_signals`` (as ``sanctions`` / ``ownership_change``
    PublicSignals) rather than through a snapshot diff.

COST / ACCESS  →  FREEMIUM, key-gated hosted API (non-commercial free tier exists)
    Hosted SaaS API is metered and needs a key for production use. The data +
    the ``yente`` matching service are free for NON-COMMERCIAL use and can be
    self-hosted (Docker: app + Elasticsearch, ~8-16 GB RAM).
    COMMERCIAL use of the data requires a paid bulk-data licence — flag this for
    production. Usable key-free for a hackathon/non-commercial demo (tighter
    rate limits).

    When ``OPENSANCTIONS_API_KEY`` is set the adapter sends
    ``Authorization: ApiKey {key}``; otherwise requests are sent unauthenticated
    (non-commercial free tier). Unlike Event Registry, the adapter does not
    silently skip — it still calls the API without a key.

    Base URL:  https://api.opensanctions.org/
    Endpoint:  GET  /search/{dataset}?q={name}&schema={schema}&limit={n}

SIGNAL FLOW
    This is a *screening* adapter, not a registry-diff adapter.
    ``fetch()`` always returns ``None`` — there is no canonical entity snapshot.
    ``fetch_signals()`` screens the given name and, via ``ubo_names`` kwarg,
    any UBO/officer names supplied by the caller:

        name hit, score ≥ 0.85 → ``sanctions``, severity=0.95 (definitive)
        name hit, score 0.70–0.85 → ``sanctions``, severity=0.75 (probable)
        UBO hit, score ≥ 0.85 → ``ownership_change``, severity=0.90
        UBO hit, score 0.70–0.85 → ``ownership_change``, severity=0.70

    Results below the 0.70 floor are discarded as too noisy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.sources.base import EntitySnapshot, PublicSignal, RegistryAdapter
from app.sources.cost import AdapterStatus, CostMixin, SourceCost

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.opensanctions.org"
_USER_AGENT = "Sentinel/1.0 (hackathon; SwissHacks 2026)"
_SIGNAL_SOURCE = "OpenSanctions"
_DEFAULT_DATASET = "default"
_SEARCH_LIMIT = 5

# Match-score thresholds.
_THRESHOLD_HIGH = 0.85   # definitive match — entity is almost certainly on the list
_THRESHOLD_LOW = 0.70    # probable match — requires manual confirmation; below → discard

# Severity values (PublicSignal.severity is a float 0..1).
_SEVERITY_CRITICAL = 0.95   # direct sanctions hit, score ≥ 0.85
_SEVERITY_HIGH = 0.75       # direct sanctions hit, score 0.70–0.85
_SEVERITY_UBO_CRITICAL = 0.90   # UBO hit, score ≥ 0.85 (indirect → slightly lower)
_SEVERITY_UBO_HIGH = 0.70       # UBO hit, score 0.70–0.85


class OpenSanctionsAdapter(CostMixin, RegistryAdapter):
    """Sanctions / PEP screening via the OpenSanctions yente API."""

    source_name = "opensanctions"
    display_name = "OpenSanctions (OFAC / EU / UN)"
    base_url = _BASE_URL
    docs_url = "https://www.opensanctions.org/docs/api/"
    cost = SourceCost.FREEMIUM
    status = AdapterStatus.PLANNED
    requires_api_key = True
    use_cases = (2, 5)
    signal_types = ("sanctions", "ownership_change")

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        # Fall back to the settings-managed key when not explicitly injected.
        self._api_key = settings.opensanctions_api_key if api_key is None else api_key
        # Accept an injected client (tests / shared pool) so the adapter does not
        # own it — never close a client the caller manages. Otherwise create one
        # here and close it in aclose(). Matches the GleifAdapter pattern.
        if client is not None:
            self._http = client
            self._owns_client = False
        else:
            self._http = httpx.AsyncClient(
                base_url=_BASE_URL, timeout=timeout
            )
            self._owns_client = True
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._backoff_base = backoff_base
        from app.core.api_cache import DiskCache
        self._cache = DiskCache("opensanctions")

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this adapter owns it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> "OpenSanctionsAdapter":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Return auth header dict when a key is configured; empty dict otherwise."""
        if self._api_key:
            return {"Authorization": f"ApiKey {self._api_key}"}
        return {}

    def record_url(self, entity_id: str) -> str | None:
        if not entity_id:
            return None
        return f"https://www.opensanctions.org/entities/{entity_id}/"

    # ------------------------------------------------------------------ #
    # Public contract                                                       #
    # ------------------------------------------------------------------ #

    async def fetch(
        self, drift_id: str, name: str, **kwargs: Any
    ) -> EntitySnapshot | None:
        """OpenSanctions is a screening source — no canonical entity snapshot."""
        return None

    async def fetch_signals(
        self, drift_id: str, name: str, since_month: int = 0, **kwargs: Any
    ) -> list[PublicSignal]:
        """Screen *name* (and optional UBO names) against OFAC/EU/UN watchlists.

        Parameters
        ----------
        drift_id : internal customer identifier.
        name : entity name to screen against the default sanctions dataset.
        since_month : zero-indexed month used as the ``month`` field on
            returned signals (signals are not time-limited — sanctions
            membership is current-state, not time-series).
        ubo_names : (kwarg) ``list[str]`` of UBO / officer names to screen
            separately. Each hit becomes an ``ownership_change`` signal with
            the UBO name in the headline. Caller obtains the list from GLEIF
            ``beneficial_owners`` / ``officers``.

        Returns [] when no hits are above the score threshold, on network
        errors, or on non-retryable HTTP errors.
        """
        signals: list[PublicSignal] = []

        # --- Screen the main entity against the Company schema ---
        try:
            hits = await self._search(name, schema="Company")
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning(
                "opensanctions_error drift_id=%s name=%r error=%s", drift_id, name, exc
            )
            return []

        for hit in hits:
            score: float = float(hit.get("score") or 0.0)
            if score < _THRESHOLD_LOW:
                continue
            caption: str = hit.get("caption") or name
            entity_id: str = hit.get("id") or ""
            signals.append(
                self._sanctions_signal(
                    caption=caption, score=score, entity_id=entity_id, month=since_month
                )
            )

        # --- UBO chain screening ---
        ubo_names: list[str] = kwargs.get("ubo_names") or []
        for ubo_name in ubo_names:
            if not ubo_name:
                continue
            try:
                # No schema filter — UBOs can be natural persons or legal entities.
                ubo_hits = await self._search(ubo_name)
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                logger.warning(
                    "opensanctions_ubo_error drift_id=%s ubo=%r error=%s",
                    drift_id, ubo_name, exc,
                )
                continue

            for hit in ubo_hits:
                score = float(hit.get("score") or 0.0)
                if score < _THRESHOLD_LOW:
                    continue
                caption = hit.get("caption") or ubo_name
                entity_id = hit.get("id") or ""
                signals.append(
                    self._ubo_signal(
                        ubo_name=ubo_name,
                        caption=caption,
                        score=score,
                        entity_id=entity_id,
                        month=since_month,
                    )
                )

        return signals

    # ------------------------------------------------------------------ #
    # HTTP helper                                                           #
    # ------------------------------------------------------------------ #

    async def _search(
        self,
        name: str,
        *,
        schema: str | None = None,
        dataset: str = _DEFAULT_DATASET,
    ) -> list[dict[str, Any]]:
        """GET /search/{dataset} with retry on 429/503; raises on other HTTP errors.

        Returns the raw ``results`` list from the API response. Transport errors
        are swallowed and return ``[]``. 429/503 after all retries are exhausted
        raises ``httpx.HTTPStatusError`` (the caller in ``fetch_signals`` converts
        it to an empty list).
        """
        cache_key = f"search:{name}:{schema or 'any'}:{dataset}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        params: dict[str, Any] = {"q": name, "limit": _SEARCH_LIMIT}
        if schema:
            params["schema"] = schema

        headers: dict[str, str] = {"User-Agent": _USER_AGENT, **self._auth_headers}

        for attempt in range(self._max_retries):
            try:
                resp = await self._http.get(
                    f"/search/{dataset}",
                    params=params,
                    headers=headers,
                )
            except httpx.TransportError:
                return []
            if resp.status_code in (429, 503) and attempt < self._max_retries - 1:
                await asyncio.sleep(self._backoff_base * (2**attempt))
                continue
            resp.raise_for_status()
            results = resp.json().get("results", [])
            self._cache.set(cache_key, results)
            return results  # type: ignore[no-any-return]
        # Unreachable — the final attempt either returns or raises above.
        raise RuntimeError("retry loop exhausted without a response")  # pragma: no cover

    # ------------------------------------------------------------------ #
    # Signal factories (pure, no I/O)                                      #
    # ------------------------------------------------------------------ #

    def _sanctions_signal(
        self,
        *,
        caption: str,
        score: float,
        entity_id: str,
        month: int,
    ) -> PublicSignal:
        if score >= _THRESHOLD_HIGH:
            headline = f"Sanctions match: {caption} (score {score:.2f})"
            severity = _SEVERITY_CRITICAL
        else:
            headline = (
                f"Probable sanctions match (manual confirmation required): "
                f"{caption} (score {score:.2f})"
            )
            severity = _SEVERITY_HIGH
        return PublicSignal(
            month=month,
            signal_type="sanctions",
            headline=headline[:200],
            severity=severity,
            source=_SIGNAL_SOURCE,
            source_url=self.record_url(entity_id),
        )

    def _ubo_signal(
        self,
        *,
        ubo_name: str,
        caption: str,
        score: float,
        entity_id: str,
        month: int,
    ) -> PublicSignal:
        is_definitive = score >= _THRESHOLD_HIGH
        severity = _SEVERITY_UBO_CRITICAL if is_definitive else _SEVERITY_UBO_HIGH
        qualifier = "match" if is_definitive else "probable match"
        headline = (
            f"UBO sanctions {qualifier}: {caption} — "
            f"screened as UBO '{ubo_name}' (score {score:.2f})"
        )
        return PublicSignal(
            month=month,
            signal_type="ownership_change",
            headline=headline[:200],
            severity=severity,
            source=_SIGNAL_SOURCE,
            source_url=self.record_url(entity_id),
            # Structured provenance so the API can surface the screened UBO name +
            # matched watchlist entity + score (Case 5) without re-parsing the
            # headline. ``kind`` tags this as a UBO-screening hit for the aggregator.
            meta={
                "kind": "ubo_screening",
                "ubo_name": ubo_name,
                "matched_entity": caption,
                "score": round(score, 2),
                "definitive": is_definitive,
            },
        )
