"""
Cost classification for source adapters — the free-vs-paid decision layer.

``base.py`` (the shared contract) is deliberately cost-agnostic: it only knows
how to fetch and diff. THIS module adds the orthogonal question the MVP cares
about: *is this source free and usable right now, or paid and skipped?*

It provides:

- :class:`SourceCost` / :class:`AdapterStatus` — the classification enums.
- :class:`SourceUnavailableError` — raised by a skipped (paid) adapter, distinct
  from ``NotImplementedError`` (a free adapter whose carcass isn't built yet).
- :class:`CostMixin` — a thin mixin (combined with
  :class:`app.sources.base.RegistryAdapter` by each concrete adapter) that carries
  the cost metadata and a ``_carcass`` helper, so every adapter declares its tier
  in one place. It is a *plain* class, not a ``RegistryAdapter`` subclass, so it
  does not trip the base class's ``source_name`` enforcement on its own.

Decision rule (enforced by tests, see ``docs/sources.md``):
    SKIPPED  <=>  PAID         — no usable free tier => not implemented
    PLANNED  <=>  FREE/FREEMIUM — open or free-tier usable => carcass now, real later
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, NoReturn

from app.sources.base import EntitySnapshot, PublicSignal

# Signal-type vocabulary the adapter layer emits via ``fetch_signals`` — the
# five categories named in the AMINA brief (kept in ``public_intel.SIGNAL_TYPES``)
# plus the registry/web change types the source adapters introduce.
#
# NOTE: these are the NOUN-form ``PublicSignal.signal_type`` values (e.g.
# ``name_change``). They are a DIFFERENT namespace from the PAST-TENSE
# ``SnapshotDiff.drift_signal_type`` routing keys produced by
# ``base.diff_snapshots`` (e.g. ``name_changed``). The future aggregator that
# turns a SnapshotDiff into a PublicSignal must map ``*_changed`` -> ``*_change``.
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
    "domain_age",
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
              implemented. ``fetch``/``fetch_signals`` raise
              :class:`SourceUnavailableError`.
    """

    PLANNED = "planned"
    SKIPPED = "skipped"


class SourceUnavailableError(RuntimeError):
    """Raised when a source is intentionally not implemented (paid/restricted).

    Distinct from ``NotImplementedError`` (a free source whose carcass simply
    hasn't been filled in yet) so callers can tell *"skipped on purpose"* from
    *"not built yet"*.
    """


class CostMixin:
    """Free-vs-paid metadata for a source adapter.

    A *plain* mixin: concrete adapters combine it with
    :class:`app.sources.base.RegistryAdapter` (``class ZefixAdapter(CostMixin,
    RegistryAdapter)``) and still implement the ``fetch`` / ``fetch_signals``
    contract. Keeping it off the ``RegistryAdapter`` inheritance chain means it
    does not trip the base class's ``source_name`` enforcement (which fires for
    any direct ``RegistryAdapter`` subclass, abstract or not).
    """

    # Provided by RegistryAdapter at runtime; annotated here so the mixin's
    # methods type-check in isolation.
    source_name: ClassVar[str]

    # --- Cost metadata (override in every concrete adapter) ---
    cost: ClassVar[SourceCost]
    status: ClassVar[AdapterStatus]
    requires_api_key: ClassVar[bool] = False
    display_name: ClassVar[str] = ""
    base_url: ClassVar[str] = ""
    docs_url: ClassVar[str] = ""
    # AMINA use-case numbers this source contributes to (see ROADMAP matrix).
    use_cases: ClassVar[tuple[int, ...]] = ()
    # PublicSignal.signal_type values this source can emit (⊆ ADAPTER_SIGNAL_TYPES).
    signal_types: ClassVar[tuple[str, ...]] = ()

    # --- Convenience predicates (classmethods so the registry can filter on
    #     adapter CLASSES without instantiating them) ---
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

    # --- Optional citation helper ---
    def record_url(self, entity_id: str) -> str | None:
        """Human-readable URL for ``entity_id`` on the source's own site.

        Default ``None``; adapters override to give the officer a click-through
        (used as ``PublicSignal.source_url`` once implemented).
        """
        return None

    # --- Carcass guard ---
    def _carcass(self) -> NoReturn:
        """Fail an unimplemented adapter body, differently by intent.

        Skipped (paid) sources raise :class:`SourceUnavailableError`; planned
        (free) sources raise ``NotImplementedError``. Concrete ``fetch`` /
        ``fetch_signals`` carcasses ``return self._carcass()``; the ``NoReturn``
        type tells the checker they never fall through.
        """
        if self.is_skipped():
            raise SourceUnavailableError(
                f"{self.source_name}: paid/restricted source, intentionally not "
                f"implemented (cost={self.cost.value}). See docs/sources.md."
            )
        raise NotImplementedError(
            f"{self.source_name}: adapter carcass — fetch/fetch_signals not yet "
            f"implemented (cost={self.cost.value}, use_cases={self.use_cases})."
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"<{type(self).__name__} source_name={self.source_name!r} "
            f"cost={self.cost.value} status={self.status.value}>"
        )


# Re-export the base types so adapter modules import everything source-related
# from one place.
__all__ = [
    "SourceCost",
    "AdapterStatus",
    "SourceUnavailableError",
    "CostMixin",
    "ADAPTER_SIGNAL_TYPES",
    "EntitySnapshot",
    "PublicSignal",
]
