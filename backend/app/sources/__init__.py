"""
app.sources — external source adapters for the Public Intelligence layer.

Status: SCAFFOLDING (carcass). This package defines the shared adapter contract
(:class:`RegistryAdapter`, :class:`EntitySnapshot`, the generic field diff) and a
carcass class per source. No adapter performs real network I/O yet — ``fetch``/
``normalize`` raise ``NotImplementedError`` (free, to-be-built) or
:class:`SourceUnavailableError` (paid, intentionally skipped).

Which sources are free and usable vs. paid-and-skipped is decided once, in
:mod:`app.sources.registry`; see ``docs/sources.md`` for the rationale.

    IMPLEMENT (free / free-tier): zefix, gleif, opensanctions, gdelt,
                                  firecrawl, wayback, whois
    SKIP (paid / restricted):     open_corporates, event_registry, crunchbase
"""

from __future__ import annotations

from app.sources.base import (
    ADAPTER_SIGNAL_TYPES,
    AdapterStatus,
    EntitySnapshot,
    FieldRule,
    PublicSignal,
    RegistryAdapter,
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
    # Contract
    "RegistryAdapter",
    "EntitySnapshot",
    "PublicSignal",
    "FieldRule",
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
