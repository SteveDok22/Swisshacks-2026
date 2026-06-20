"""
sources/base.py — shared foundation for all external registry adapters.

This module defines three things:

1. EntitySnapshot — pure-Python domain object returned by adapters.
   One point-in-time capture of an entity's KYC state fetched from a
   registry. Decoupled from SQLAlchemy so adapters have no DB dependency;
   the service layer converts to EntitySnapshotDB for persistence.

2. PublicSignal — canonical definition of one external intelligence signal.
   Moved here from drift/public_intel.py so every adapter produces the same
   type. Adds source_url (the P1 "source citations" gap listed in ROADMAP).
   public_intel.py now imports from here.

3. SnapshotDiff + diff_snapshots() — the diff pattern.
   Compares a baseline EntitySnapshot against a current one and returns a
   list of structured changes, each carrying a drift_signal_type and severity
   so the engine can route them to the right use-case handler:

       name_changed          → Case 8  (legal entity name change)
       legal_form_changed    → Case 4  (jurisdiction / legal form change)
       jurisdiction_changed  → Case 4
       address_changed       → Case 4
       dissolution_status_changed → Cases 4, 7
       ubo_added / ubo_removed    → Case 5  (new shareholders / UBOs)
       officer_added / officer_removed → Case 5

4. RegistryAdapter — ABC every concrete adapter must implement.
   Enforces the two-method contract (fetch + fetch_signals) and declares
   source_name as a required class variable so the diff layer can tag every
   EntitySnapshot with its provenance.

Dependency rule: this file must NOT import from app.db or app.drift so that
adapters remain independent of the ORM and the drift engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

# ---------------------------------------------------------------------------
# EntitySnapshot — pure-Python domain object
# ---------------------------------------------------------------------------

@dataclass
class EntitySnapshot:
    """
    One point-in-time KYC state for a customer, as fetched from an external
    registry (or the internal bank record).

    Adapters return this type; the service layer persists it via
    db.kyc_baseline.store_snapshot() after converting to EntitySnapshotDB.
    Keeping the two types separate means adapters need no SQLAlchemy import.
    """

    drift_id: str
    name: str
    source: str  # adapter source_name value, e.g. "zefix"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # === Legal identity ===
    legal_form: str | None = None
    # ISO 3166-1 alpha-2 by convention; a single-country register may instead
    # store a sub-national code (e.g. ZEFIX writes the Swiss canton "ZG").
    # diff_snapshots compares this field as-is, so a baseline and current
    # snapshot MUST come from the same source for the comparison to be valid.
    jurisdiction: str | None = None
    registered_address: str | None = None
    # "active" | "dissolved" | "dormant" | "struck_off" | None
    dissolution_status: str | None = None

    # === Ownership & control ===
    # Free-text names, LEI codes, or UUID strings. The contagion layer links
    # these to graph nodes; the diff layer compares them as sets.
    beneficial_owners: list[str] = field(default_factory=list)
    officers: list[str] = field(default_factory=list)

    # === Raw source payload ===
    # Full adapter response — nothing is discarded. Structure varies per source.
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Deduplicate while preserving order (first occurrence wins).
        # Adapters may return dirty data with repeated names; set-diff in
        # diff_snapshots would otherwise silently drop genuine removals.
        self.beneficial_owners = list(dict.fromkeys(self.beneficial_owners))
        self.officers = list(dict.fromkeys(self.officers))


# ---------------------------------------------------------------------------
# PublicSignal — canonical external signal definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PublicSignal:
    """
    One external public-intelligence signal about a customer at a point in time.

    Canonical definition shared by all adapters and by drift/public_intel.py.
    source_url is the P1 gap noted in ROADMAP ("Source citations on signal cards").
    """

    month: int
    signal_type: str   # "news" | "sanctions" | "adverse_media" | "ownership_change" | "funding_event"
    headline: str
    severity: float    # 0..1 from lexicon or source-provided confidence
    source: str        # human-readable source name, e.g. "Reuters" or "OFAC"
    source_url: str | None = None  # deep-link to the original record

    def __post_init__(self) -> None:
        if not (0.0 <= self.severity <= 1.0):
            raise ValueError(f"severity must be in [0, 1], got {self.severity}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "signal_type": self.signal_type,
            "headline": self.headline,
            "severity": round(self.severity, 2),
            "source": self.source,
            "source_url": self.source_url,
        }


# ---------------------------------------------------------------------------
# SnapshotDiff — one detected change between two snapshots
# ---------------------------------------------------------------------------

# Severity weights per field — higher means more operationally significant.
# These map directly to AMINA use cases (see module docstring).
_FIELD_SEVERITY: dict[str, float] = {
    "dissolution_status": 0.90,   # dissolution or reactivation (Cases 4, 7)
    "jurisdiction": 0.80,         # legal jurisdiction shift (Case 4)
    "name": 0.70,                 # entity renamed (Case 8)
    "legal_form": 0.65,           # structural change (Case 4)
    "registered_address": 0.40,   # address move (Case 4)
}

# Severity for ownership list changes
_UBO_ADDED_SEVERITY = 0.60      # new UBO added (Case 5)
_UBO_REMOVED_SEVERITY = 0.55    # UBO disappeared (Case 5)
_OFFICER_ADDED_SEVERITY = 0.45  # new officer (Case 5)
_OFFICER_REMOVED_SEVERITY = 0.40  # officer left (Case 5)

# Ordered list of (field_name, drift_signal_type) for scalar diff.
# Order is arbitrary — callers sort output by severity if priority matters.
# Must stay aligned with _FIELD_SEVERITY keys above.
_SCALAR_CHECKS: tuple[tuple[str, str], ...] = (
    ("name",               "name_changed"),
    ("legal_form",         "legal_form_changed"),
    ("jurisdiction",       "jurisdiction_changed"),
    ("registered_address", "address_changed"),
    ("dissolution_status", "dissolution_status_changed"),
)


@dataclass
class SnapshotDiff:
    """
    One structural change detected between two EntitySnapshots.

    drift_signal_type maps to a use case so the engine can route it:
        name_changed, legal_form_changed, jurisdiction_changed,
        address_changed, dissolution_status_changed,
        ubo_added, ubo_removed, officer_added, officer_removed
    """

    field: str                 # which attribute changed
    old_value: Any             # value in the baseline (None for list additions)
    new_value: Any             # value in the current snapshot (None for removals)
    drift_signal_type: str     # machine-readable change category
    severity: float            # 0..1 operational significance

    def __post_init__(self) -> None:
        if not (0.0 <= self.severity <= 1.0):
            raise ValueError(f"severity must be in [0, 1], got {self.severity}")


def diff_snapshots(
    baseline: EntitySnapshot,
    current: EntitySnapshot,
) -> list[SnapshotDiff]:
    """
    Compare two EntitySnapshots and return every detected structural change.

    Rules:
    - Scalar fields: any value change (including None ↔ value) is reported.
      Two None values produce no diff — the field was unknown in both states
      and nothing changed.
    - List fields (beneficial_owners, officers): set-diffed so order changes
      are ignored; only genuine additions and removals are reported.

    The list is unordered; callers that need priority ordering should sort by
    severity descending.
    """
    diffs: list[SnapshotDiff] = []

    # --- Scalar fields ---
    for attr, signal_type in _SCALAR_CHECKS:
        old_val = getattr(baseline, attr)
        new_val = getattr(current, attr)
        if old_val == new_val:  # covers None == None
            continue
        diffs.append(
            SnapshotDiff(
                field=attr,
                old_value=old_val,
                new_value=new_val,
                drift_signal_type=signal_type,
                severity=_FIELD_SEVERITY[attr],
            )
        )

    # --- Beneficial owners (UBOs) ---
    old_ubos = set(baseline.beneficial_owners)
    new_ubos = set(current.beneficial_owners)
    for added in sorted(new_ubos - old_ubos):
        diffs.append(
            SnapshotDiff(
                field="beneficial_owners",
                old_value=None,
                new_value=added,
                drift_signal_type="ubo_added",
                severity=_UBO_ADDED_SEVERITY,
            )
        )
    for removed in sorted(old_ubos - new_ubos):
        diffs.append(
            SnapshotDiff(
                field="beneficial_owners",
                old_value=removed,
                new_value=None,
                drift_signal_type="ubo_removed",
                severity=_UBO_REMOVED_SEVERITY,
            )
        )

    # --- Officers ---
    old_officers = set(baseline.officers)
    new_officers = set(current.officers)
    for added in sorted(new_officers - old_officers):
        diffs.append(
            SnapshotDiff(
                field="officers",
                old_value=None,
                new_value=added,
                drift_signal_type="officer_added",
                severity=_OFFICER_ADDED_SEVERITY,
            )
        )
    for removed in sorted(old_officers - new_officers):
        diffs.append(
            SnapshotDiff(
                field="officers",
                old_value=removed,
                new_value=None,
                drift_signal_type="officer_removed",
                severity=_OFFICER_REMOVED_SEVERITY,
            )
        )

    return diffs


# ---------------------------------------------------------------------------
# RegistryAdapter — ABC for all external source adapters
# ---------------------------------------------------------------------------

class RegistryAdapter(ABC):
    """
    Abstract base class for every external registry adapter.

    Concrete adapters (zefix.py, gleif.py, …) inherit from this class and
    implement two methods:

        fetch()         — retrieve the current EntitySnapshot from the source
        fetch_signals() — retrieve recent PublicSignals for the entity

    The class variable source_name MUST be set on each concrete subclass so
    the provenance of every snapshot and signal is unambiguous.

    Lifecycle: adapters are stateless (no session state); the service layer
    instantiates one per request or reuses a shared instance. HTTP sessions,
    API keys, and rate-limiter state are set up in __init__ by each adapter.
    """

    source_name: ClassVar[str]  # subclasses MUST set this, e.g. "zefix"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Enforce source_name on every non-abstract subclass.
        # Check cls.__dict__ first (set on this class), then fall back to
        # inherited value (concrete parent set it, child can omit it).
        # hasattr() is intentionally avoided — it finds the ClassVar annotation
        # on RegistryAdapter itself and returns True even for subclasses that
        # never assigned the variable, masking the missing-value error.
        if not getattr(cls, "__abstractmethods__", None):
            source_name = cls.__dict__.get("source_name") or getattr(cls, "source_name", None)
            if not (source_name and str(source_name).strip()):
                raise TypeError(
                    f"{cls.__name__} must define a non-empty class variable "
                    f"`source_name` (e.g. source_name = 'zefix')"
                )

    @abstractmethod
    async def fetch(
        self,
        drift_id: str,
        name: str,
        **kwargs: Any,
    ) -> EntitySnapshot | None:
        """
        Fetch the current entity state from this registry.

        Returns None if the entity is not found in this source — callers must
        handle the None case (the entity may simply not be registered with this
        particular authority).

        Parameters
        ----------
        drift_id:
            Internal identifier for the customer (drift engine ID or UUID).
        name:
            Entity name used for registry lookup when no structured ID is
            available (e.g. company name for ZEFIX full-text search).
        **kwargs:
            Adapter-specific lookup parameters, e.g.:
              lei=       for GLEIF
              uid=       for ZEFIX (Swiss company UID)
              jurisdiction= for OpenCorporates
        """

    @abstractmethod
    async def fetch_signals(
        self,
        drift_id: str,
        name: str,
        since_month: int = 0,
        **kwargs: Any,
    ) -> list[PublicSignal]:
        """
        Fetch recent public signals for this entity from the registry.

        Returns an empty list if no signals are available (never raises for
        absence of data — only raises for network / auth errors).

        Parameters
        ----------
        drift_id:
            Internal customer identifier.
        name:
            Entity name used for news / event lookup.
        since_month:
            Zero-indexed month floor; only signals at or after this month are
            returned. Lets the aggregator request incremental updates without
            re-fetching the full history on every scan.
        **kwargs:
            Adapter-specific parameters.
        """
