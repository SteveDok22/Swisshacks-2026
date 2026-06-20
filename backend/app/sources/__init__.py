"""
app.sources — external source adapters for the Public Intelligence layer.

Status: SCAFFOLDING (carcass). ``base.py`` (the shared contract — EntitySnapshot,
PublicSignal, SnapshotDiff/diff_snapshots, the RegistryAdapter ABC) is built out;
``cost.py`` layers the free-vs-paid classification on top; and there is a carcass
class per source whose ``fetch``/``fetch_signals`` raise ``NotImplementedError``
(free, to-be-built) or ``SourceUnavailableError`` (paid, intentionally skipped).

Which sources are free and usable vs. paid-and-skipped is decided once, in
:mod:`app.sources.registry`; see ``docs/sources.md`` for the rationale.

    IMPLEMENT (free / free-tier): zefix, gleif, opensanctions, gdelt,
                                  firecrawl, wayback, whois
    SKIP (paid / restricted):     open_corporates, event_registry, crunchbase
"""

from app.sources.base import (
    EntitySnapshot,
    PublicSignal,
    RegistryAdapter,
    SnapshotDiff,
    diff_snapshots,
)
from app.sources.cost import (
    ADAPTER_SIGNAL_TYPES,
    AdapterStatus,
    CostMixin,
    SourceCost,
    SourceUnavailableError,
)
from app.sources.crunchbase import CrunchbaseAdapter
from app.sources.event_registry import EventRegistryAdapter
from app.sources.firecrawl import FirecrawlAdapter
from app.sources.gdelt import GdeltAdapter
from app.sources.gleif import GleifAdapter
from app.sources.open_corporates import OpenCorporatesAdapter
from app.sources.opensanctions import OpenSanctionsAdapter
from app.sources.registry import (
    ALL_ADAPTERS,
    REGISTRY,
    catalogue,
    get_adapter,
    skipped_adapters,
    usable_adapters,
)
from app.sources.wayback import WaybackAdapter
from app.sources.whois import WhoisAdapter
from app.sources.zefix import ZefixAdapter

__all__ = [
    # Contract (base.py)
    "RegistryAdapter",
    "EntitySnapshot",
    "PublicSignal",
    "SnapshotDiff",
    "diff_snapshots",
    # Cost layer (cost.py)
    "CostMixin",
    "SourceCost",
    "AdapterStatus",
    "SourceUnavailableError",
    "ADAPTER_SIGNAL_TYPES",
    # Registry
    "ALL_ADAPTERS",
    "REGISTRY",
    "get_adapter",
    "usable_adapters",
    "skipped_adapters",
    "catalogue",
    # Adapters
    "ZefixAdapter",
    "GleifAdapter",
    "OpenSanctionsAdapter",
    "OpenCorporatesAdapter",
    "GdeltAdapter",
    "EventRegistryAdapter",
    "CrunchbaseAdapter",
    "FirecrawlAdapter",
    "WaybackAdapter",
    "WhoisAdapter",
]
