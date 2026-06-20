"""
Source-adapter foundations — the carcass every external connector builds on.

AMINA Challenge 4 asks the Public Intelligence layer (Layer 2) to draw on
*real* external sources — commercial registers, the global LEI system, sanctions
lists, news, funding feeds, website history — and turn each observed change into
a ``PublicSignal`` the drift engine can fuse with internal bank data.

This module defines the **shared contract**, not any single source. Every
connector in ``app.sources`` is a :class:`RegistryAdapter` and follows the same
four-step pipeline:

    fetch(entity_id) -> raw dict
        normalize(raw) -> EntitySnapshot          (a comparable, canonical view)
            diff(baseline, current) -> [PublicSignal]   (only what changed)

``fetch_and_diff`` chains the three against a stored KYC baseline so the engine
can ask one question per source: *"what is different now versus onboarding?"*

Scope of THIS file: interfaces and the generic field-diff fundamentals only.
The concrete adapters are carcasses — their ``fetch``/``normalize`` raise until
implemented (free sources) or are intentionally skipped (paid sources). See
:data:`app.sources.registry.REGISTRY` for the free-vs-paid decision per source
and ``docs/sources.md`` for the rationale.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, NoReturn

from app.drift.public_intel import PublicSignal

__all__ = [
    "SourceCost",
    "AdapterStatus",
    "SourceUnavailableError",
    "EntitySnapshot",
    "FieldRule",
    "RegistryAdapter",
    "RawRecord",
    "ADAPTER_SIGNAL_TYPES",
    "PublicSignal",
]

# A raw upstream payload as returned by ``fetch`` (JSON object, RDAP record, ...).
RawRecord = dict[str, Any]

# Signal types the adapter layer can emit. A superset of the five named in the
# AMINA brief (kept in ``public_intel.SIGNAL_TYPES``) plus the registry/web
# change types the source adapters introduce.
ADAPTER_SIGNAL_TYPES = (
    "news",
    "sanctions",
    "adverse_media",
    "ownership_change",
    "funding_event",
    "name_change",
    "legal_form_change",
    "jurisdiction_change",
    "address_change",
    "status_change",
    "domain_change",
    "business_model_change",
    "dormancy_break",
)


class SourceCost(StrEnum):
    """How much a source costs to use in production.

    FREE      — open API/data, no key, usable for real (ZEFIX, GLEIF, RDAP, ...).
    FREEMIUM  — free tier or free self-host, but a key and/or limits apply
                (OpenSanctions hosted API, Firecrawl).
    PAID      — no usable free tier; requires a paid plan or approval-gated
                access (OpenCorporates, Event Registry, Crunchbase).
    """

    FREE = "free"
    FREEMIUM = "freemium"
    PAID = "paid"


class AdapterStatus(StrEnum):
    """Whether we intend to actually implement this adapter for the MVP.

    PLANNED — free or free-tier usable today; carcass now, real fetch later.
    SKIPPED — paid/restricted; the carcass documents it but it will NOT be
              implemented. ``fetch`` raises :class:`SourceUnavailableError`.
    """

    PLANNED = "planned"
    SKIPPED = "skipped"


class SourceUnavailableError(RuntimeError):
    """Raised when a source is intentionally not implemented (paid/restricted).

    Distinct from ``NotImplementedError`` (a free source whose carcass simply
    hasn't been filled in yet) so callers can tell *"skipped on purpose"* from
    *"not built yet"*.
    """


@dataclass
class EntitySnapshot:
    """A canonical, comparable view of one entity at one point in time.

    Adapters normalize wildly different upstream payloads (ZEFIX XML-ish JSON,
    GLEIF JSON:API, RDAP, ...) into this single shape so :meth:`RegistryAdapter.diff`
    can compare onboarding-baseline against current with one code path.

    Every field except ``entity_id``/``source_id`` is optional: no single source
    populates all of them (RDAP has a domain but no legal form; ZEFIX has a legal
    form but no domain). ``None`` means "this source does not report this field"
    and is never treated as a change.
    """

    entity_id: str
    source_id: str
    legal_name: str | None = None
    legal_form: str | None = None
    jurisdiction: str | None = None
    registered_address: str | None = None
    status: str | None = None
    owners: list[str] = field(default_factory=list)
    domain: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Citation URL for the human-readable record on the source's own site.
    source_url: str | None = None
    # Untouched upstream payload, for audit/debug and adapter-specific diffing.
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "source_id": self.source_id,
            "legal_name": self.legal_name,
            "legal_form": self.legal_form,
            "jurisdiction": self.jurisdiction,
            "registered_address": self.registered_address,
            "status": self.status,
            "owners": list(self.owners),
            "domain": self.domain,
            "fetched_at": self.fetched_at.isoformat(),
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class FieldRule:
    """Maps a changed :class:`EntitySnapshot` field to a ``PublicSignal``.

    The generic diff walks these rules: if ``getattr(baseline, field)`` differs
    from ``getattr(current, field)`` (and neither side is ``None``), it emits a
    signal of ``signal_type`` at ``severity``. Subclasses override
    :attr:`RegistryAdapter.field_rules` (or :meth:`RegistryAdapter.diff` whole)
    to apply source-specific severity formulas.
    """

    field: str
    signal_type: str
    severity: float
    headline: str  # ``str.format`` template; gets ``old=`` and ``new=`` kwargs


class RegistryAdapter(ABC):
    """Abstract base for every external source connector.

    Subclasses declare metadata (``source_id``, ``base_url``, :attr:`cost`,
    :attr:`status`, ``use_cases``) and implement :meth:`fetch` + :meth:`normalize`.
    They inherit a generic field-level :meth:`diff` and the :meth:`fetch_and_diff`
    orchestration; either can be overridden when a source needs bespoke logic
    (e.g. embedding-distance for website drift, match-score for sanctions).
    """

    # --- Metadata (override in every subclass) ---
    source_id: str = ""
    display_name: str = ""
    base_url: str = ""
    docs_url: str = ""
    cost: SourceCost = SourceCost.FREE
    status: AdapterStatus = AdapterStatus.PLANNED
    requires_api_key: bool = False
    # AMINA use-case numbers this source contributes to (see ROADMAP matrix).
    use_cases: tuple[int, ...] = ()
    # Signal types this source can emit (subset of ADAPTER_SIGNAL_TYPES).
    signal_types: tuple[str, ...] = ()

    # Default generic diff rules. ``owners`` is handled separately (set diff).
    field_rules: tuple[FieldRule, ...] = (
        FieldRule("legal_name", "name_change", 0.85,
                  "Legal name changed: '{old}' -> '{new}'"),
        FieldRule("legal_form", "legal_form_change", 0.70,
                  "Legal form changed: '{old}' -> '{new}'"),
        FieldRule("jurisdiction", "jurisdiction_change", 0.70,
                  "Jurisdiction changed: '{old}' -> '{new}'"),
        FieldRule("registered_address", "address_change", 0.55,
                  "Registered address changed: '{old}' -> '{new}'"),
        FieldRule("status", "status_change", 0.60,
                  "Status changed: '{old}' -> '{new}'"),
        FieldRule("domain", "domain_change", 0.70,
                  "Primary domain changed: '{old}' -> '{new}'"),
    )

    # --- Convenience predicates ---
    # Classmethods (not properties) because ``cost``/``status`` are class
    # attributes — this lets both instances AND the registry's class-level
    # filters (usable_adapters/skipped_adapters) share one implementation.
    @classmethod
    def is_free(cls) -> bool:
        return cls.cost is SourceCost.FREE

    @classmethod
    def is_skipped(cls) -> bool:
        return cls.status is AdapterStatus.SKIPPED

    @classmethod
    def is_usable(cls) -> bool:
        """True when we intend to run this source (free or free-tier)."""
        return cls.status is AdapterStatus.PLANNED

    # --- The contract every concrete adapter implements ---
    @abstractmethod
    def fetch(self, entity_id: str) -> RawRecord:
        """Fetch the current raw record for ``entity_id`` from the source.

        Carcasses raise: ``NotImplementedError`` for a planned (free) source,
        or :class:`SourceUnavailableError` for a skipped (paid) one.
        """

    @abstractmethod
    def normalize(self, raw: RawRecord) -> EntitySnapshot:
        """Map a raw upstream payload onto the canonical :class:`EntitySnapshot`."""

    # --- Shared, overridable fundamentals ---
    def entity_url(self, entity_id: str) -> str | None:
        """Human-readable citation URL for ``entity_id`` on the source's site.

        Default: ``None``. Adapters override to give the officer a click-through
        (e.g. ``https://www.zefix.admin.ch/.../{uid}``).
        """
        return None

    def diff(
        self,
        baseline: EntitySnapshot,
        current: EntitySnapshot,
        *,
        month: int = 0,
    ) -> list[PublicSignal]:
        """Generic field-by-field diff: emit one ``PublicSignal`` per change.

        Compares the canonical fields named in :attr:`field_rules` plus the
        ``owners`` set. A field is "changed" only when both sides are non-``None``
        and unequal — a source that does not report a field never fabricates a
        change. ``month`` is the customer-window index the integration layer
        assigns; carcass/unit use defaults to 0.
        """
        signals: list[PublicSignal] = []
        url = current.source_url or self.entity_url(current.entity_id)
        source = self.display_name or self.source_id

        for rule in self.field_rules:
            # No getattr default: ``rule.field`` must be a real EntitySnapshot
            # attribute. A typo'd/stale field should fail loudly here, not
            # silently disable a whole signal class.
            old = getattr(baseline, rule.field)
            new = getattr(current, rule.field)
            if old is None or new is None or old == new:
                continue
            signals.append(
                PublicSignal(
                    month=month,
                    signal_type=rule.signal_type,
                    headline=rule.headline.format(old=old, new=new),
                    severity=rule.severity,
                    source=source,
                    source_url=url,
                    raw_evidence={"field": rule.field, "old": old, "new": new},
                )
            )

        # Ownership is a set, not a scalar. Both directions are AML-relevant:
        # a NEW beneficial owner/officer and a DEPARTING one each signal control
        # drift. Hoist the membership sets out of the loops (O(n+m), not O(n*m)).
        baseline_owners = set(baseline.owners)
        current_owners = set(current.owners)
        for owner in (o for o in current.owners if o not in baseline_owners):
            signals.append(
                PublicSignal(
                    month=month, signal_type="ownership_change",
                    headline=f"New owner/officer recorded: {owner}",
                    severity=0.50, source=source, source_url=url,
                    raw_evidence={"field": "owners", "added": owner},
                )
            )
        for owner in (o for o in baseline.owners if o not in current_owners):
            signals.append(
                PublicSignal(
                    month=month, signal_type="ownership_change",
                    headline=f"Owner/officer no longer recorded: {owner}",
                    severity=0.50, source=source, source_url=url,
                    raw_evidence={"field": "owners", "removed": owner},
                )
            )

        return signals

    def fetch_and_diff(
        self,
        entity_id: str,
        baseline: EntitySnapshot,
        *,
        month: int = 0,
    ) -> list[PublicSignal]:
        """fetch -> normalize -> diff against ``baseline``. The engine entry point.

        Skipped (paid) sources fail fast with :class:`SourceUnavailableError`
        before any network call.
        """
        if self.is_skipped():
            raise SourceUnavailableError(
                f"{self.source_id}: paid/restricted source, skipped for the MVP"
            )
        raw = self.fetch(entity_id)
        current = self.normalize(raw)
        return self.diff(baseline, current, month=month)

    # --- Carcass helpers ---
    def _carcass(self) -> NoReturn:
        """Guard for unimplemented adapter bodies — always raises.

        Skipped (paid) sources raise :class:`SourceUnavailableError`; planned
        (free) sources raise ``NotImplementedError``. Concrete ``fetch``/
        ``normalize`` carcasses ``return self._carcass()`` so the free-vs-paid
        intent is explicit and uniform; the ``NoReturn`` type tells the checker
        the method never falls through, so no unreachable filler is needed.
        """
        if self.is_skipped():
            raise SourceUnavailableError(
                f"{self.source_id}: paid/restricted source, intentionally not "
                f"implemented (cost={self.cost.value}). See docs/sources.md."
            )
        raise NotImplementedError(
            f"{self.source_id}: adapter carcass — fetch/normalize not yet "
            f"implemented (cost={self.cost.value}, use_cases={self.use_cases})."
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"<{type(self).__name__} source_id={self.source_id!r} "
            f"cost={self.cost.value} status={self.status.value}>"
        )
