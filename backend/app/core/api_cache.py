"""
Disk-based API response cache.

All external HTTP responses and library call results are serialised to JSON
under api_cache_dir/{service}/{key}.json and committed to the repo.  This lets
"live" entities (mode="live") work fully offline — the engine reads from the
cache instead of hitting the network, so the demo never depends on external
uptime.

Write-through: a cache miss triggers a live call; the response is saved
immediately so the next run is instant.  Cache files survive container
rebuilds because they live in the bind-mounted source tree, not in the
ephemeral container layer.

Usage (GDELT DataFrames)
------------------------
    cache = DiskCache("gdelt")
    df = cache.get_df("timeline:Temenos AG:timelinevolraw:12m")
    if df is None:
        df = gd.timeline_search(...)
        cache.set_df("timeline:Temenos AG:timelinevolraw:12m", df)

Usage (raw dicts / JSON responses)
-----------------------------------
    cache = DiskCache("gleif")
    data = cache.get("lei:213800QIEHL1NL42HL79")
    if data is None:
        data = await http.get(url).json()
        cache.set("lei:213800QIEHL1NL42HL79", data)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)


def _cache_key(raw: str) -> str:
    """Stable 20-hex-char cache key derived from an arbitrary string."""
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


class DiskCache:
    """Per-service disk cache backed by JSON files.

    Parameters
    ----------
    service:
        Sub-directory name under api_cache_dir (e.g. ``"gdelt"``, ``"gleif"``).
    """

    def __init__(self, service: str) -> None:
        self._dir = Path(settings.api_cache_dir) / service
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / f"{_cache_key(key)}.json"

    # ------------------------------------------------------------------
    # Raw JSON (dicts, lists, primitives)
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return the cached value or None on a miss."""
        p = self._path(key)
        if not p.exists():
            return None
        try:
            envelope = json.loads(p.read_text(encoding="utf-8"))
            return envelope.get("data")
        except Exception as exc:
            logger.warning("api_cache_read_error", extra={"key": key, "exc": str(exc)})
            return None

    def set(self, key: str, data: Any) -> None:
        """Persist *data* under *key*. Silently ignores serialisation errors."""
        p = self._path(key)
        try:
            p.write_text(
                json.dumps(
                    {
                        "key_raw": key,
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                        "data": data,
                    },
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("api_cache_write_error", extra={"key": key, "exc": str(exc)})

    # ------------------------------------------------------------------
    # pandas DataFrames (GDELT timelines + article lists)
    # ------------------------------------------------------------------

    def get_df(self, key: str) -> pd.DataFrame | None:
        """Return a cached DataFrame or None on a miss."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return pd.DataFrame(raw["records"], columns=raw["columns"])
        except Exception as exc:
            logger.warning("api_cache_df_parse_error", extra={"key": key, "exc": str(exc)})
            return None

    def set_df(self, key: str, df: pd.DataFrame) -> None:
        """Persist a DataFrame as a list-of-records envelope."""
        if df is None or df.empty:
            return
        try:
            self.set(
                key,
                {
                    "columns": list(df.columns),
                    "records": json.loads(df.to_json(orient="records", date_format="iso")),
                },
            )
        except Exception as exc:
            logger.warning("api_cache_df_write_error", extra={"key": key, "exc": str(exc)})
