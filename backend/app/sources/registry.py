"""
Source registry — the single catalogue of every adapter and its free/paid status.

This is the lookup the (future) integration layer in ``drift/public_intel.py``
uses to decide which sources to actually run: iterate :func:`usable_adapters`
(free / free-tier, ``status == PLANNED``) and never the :func:`skipped_adapters`
(paid / restricted). Keeping the decision in one place means the engine, the
tests, the API and ``docs/sources.md`` all agree on what is free and usable.

Decision rule (see ``docs/sources.md`` for the per-source rationale):
    SKIPPED  <=>  PAID        — no usable free tier => not implemented
    PLANNED  <=>  FREE/FREEMIUM — open or free-tier usable => carcass now, real later
"""

from __future__ import annotations

from app.sources.base import AdapterStatus, RegistryAdapter, SourceCost
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
ALL_ADAPTERS: tuple[type[RegistryAdapter], ...] = (
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

# source_id -> adapter class
REGISTRY: dict[str, type[RegistryAdapter]] = {a.source_id: a for a in ALL_ADAPTERS}


def get_adapter(source_id: str) -> type[RegistryAdapter]:
    """Return the adapter class for ``source_id`` (raises KeyError if unknown)."""
    return REGISTRY[source_id]


def usable_adapters() -> tuple[type[RegistryAdapter], ...]:
    """Adapters we intend to run — free or free-tier (``status == PLANNED``)."""
    return tuple(a for a in ALL_ADAPTERS if a.status is AdapterStatus.PLANNED)


def skipped_adapters() -> tuple[type[RegistryAdapter], ...]:
    """Adapters intentionally not implemented — paid/restricted (``SKIPPED``)."""
    return tuple(a for a in ALL_ADAPTERS if a.status is AdapterStatus.SKIPPED)


def catalogue() -> list[dict]:
    """Serializable catalogue of every source — for docs and the API surface."""
    return [
        {
            "source_id": a.source_id,
            "display_name": a.display_name,
            "cost": a.cost.value,
            "status": a.status.value,
            "requires_api_key": a.requires_api_key,
            "is_free": a.cost is SourceCost.FREE,
            "use_cases": list(a.use_cases),
            "signal_types": list(a.signal_types),
            "base_url": a.base_url,
            "docs_url": a.docs_url,
        }
        for a in ALL_ADAPTERS
    ]
