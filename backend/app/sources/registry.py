"""
Source registry — the single catalogue of every adapter and its free/paid status.

This is the lookup the (future) integration layer in ``drift/public_intel.py``
uses to decide which sources to actually run: iterate :func:`usable_adapters`
(free / free-tier, ``status == PLANNED``) and never the :func:`skipped_adapters`
(paid / restricted). Keeping the decision in one place means the engine, the
tests, the API and ``docs/sources.md`` all agree on what is free and usable.

Decision rule (see ``docs/sources.md`` for the per-source rationale):
    SKIPPED  <=>  PAID         — no usable free tier => not implemented
    PLANNED  <=>  FREE/FREEMIUM — open or free-tier usable => carcass now, real later
"""

from __future__ import annotations

from typing import Any

from app.sources.cost import CostMixin, SourceCost
from app.sources.crunchbase import CrunchbaseAdapter
from app.sources.event_registry import EventRegistryAdapter
from app.sources.firecrawl import FirecrawlAdapter
from app.sources.gdelt import GdeltAdapter
from app.sources.gleif import GleifAdapter
from app.sources.open_corporates import OpenCorporatesAdapter
from app.sources.opensanctions import OpenSanctionsAdapter
from app.sources.wayback import WaybackAdapter
from app.sources.whois import WhoisAdapter
from app.sources.zefix import ZefixAdapter

# Every adapter the project knows about, in roughly the order they appear in the
# source-integration architecture (registry -> screening -> news -> web).
ALL_ADAPTERS: tuple[type[CostMixin], ...] = (
    ZefixAdapter,
    GleifAdapter,
    OpenSanctionsAdapter,
    OpenCorporatesAdapter,
    GdeltAdapter,
    EventRegistryAdapter,
    CrunchbaseAdapter,
    FirecrawlAdapter,
    WaybackAdapter,
    WhoisAdapter,
)

# source_name -> adapter class
REGISTRY: dict[str, type[CostMixin]] = {a.source_name: a for a in ALL_ADAPTERS}


def get_adapter(source_name: str) -> type[CostMixin]:
    """Return the adapter class for ``source_name`` (raises KeyError if unknown)."""
    return REGISTRY[source_name]


def usable_adapters() -> tuple[type[CostMixin], ...]:
    """Adapters we intend to run — free or free-tier (``status == PLANNED``)."""
    return tuple(a for a in ALL_ADAPTERS if a.is_usable())


def skipped_adapters() -> tuple[type[CostMixin], ...]:
    """Adapters intentionally not implemented — paid/restricted (``SKIPPED``)."""
    return tuple(a for a in ALL_ADAPTERS if a.is_skipped())


def catalogue() -> list[dict[str, Any]]:
    """Serializable catalogue of every source — for docs and the API surface."""
    return [
        {
            "source_name": a.source_name,
            "display_name": a.display_name,
            "cost": a.cost.value,
            "status": a.status.value,
            "requires_api_key": a.requires_api_key,
            "is_free": a.is_free(),
            "use_cases": list(a.use_cases),
            "signal_types": list(a.signal_types),
            "base_url": a.base_url,
            "docs_url": a.docs_url,
        }
        for a in ALL_ADAPTERS
    ]


# Re-export for convenience.
__all__ = [
    "ALL_ADAPTERS",
    "REGISTRY",
    "SourceCost",
    "get_adapter",
    "usable_adapters",
    "skipped_adapters",
    "catalogue",
]
