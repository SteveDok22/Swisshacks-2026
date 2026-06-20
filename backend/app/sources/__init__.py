"""
Source adapters — external registry integrations.

Each adapter implements RegistryAdapter and is responsible for one external
data source (ZEFIX, GLEIF, OpenSanctions, OpenCorporates, etc.).

Public re-exports from base.py so callers can do:
    from app.sources import RegistryAdapter, EntitySnapshot, PublicSignal
"""

from app.sources.base import (
    EntitySnapshot,
    PublicSignal,
    RegistryAdapter,
    SnapshotDiff,
    diff_snapshots,
)

__all__ = [
    "EntitySnapshot",
    "PublicSignal",
    "RegistryAdapter",
    "SnapshotDiff",
    "diff_snapshots",
]
