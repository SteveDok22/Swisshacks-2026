"""
Database seeding — seeds KYC baselines from the synthetic drift book at startup.

Phase A decision: mock_data.py clients/cases are kept dormant (not deleted, not
called). The drift book is the whole demo; the case-review workspace at /cases
is kept for reference but not pre-populated.
Idempotent: only runs if entity_snapshots table is empty.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.db.kyc_baseline import EntitySnapshotDB, store_snapshot
from app.drift.simulator import generate_book

logger = get_logger(__name__)


async def seed_if_empty(session: AsyncSession) -> bool:
    """
    Seed KYC baselines from the synthetic drift book if the snapshots table is empty.

    Returns True if seeding happened, False if skipped.
    """
    # Check if already seeded (use entity_snapshots — no clients are seeded in
    # drift-only mode so ClientDB is always empty and cannot serve as the guard).
    result = await session.execute(select(EntitySnapshotDB).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("seed_skipped", reason="already_populated")
        return False

    logger.info("seed_starting")

    # === Seed KYC baselines from the synthetic drift book ===
    await _seed_kyc_baselines(session)

    await session.commit()

    logger.info("seed_completed")
    return True


def _mean_of_windows(windows: list) -> float | None:
    """Mean of per-window means. Returns None for an empty window list."""
    if not windows:
        return None
    return float(np.mean([w.mean() for w in windows]))


def _synthetic_lei(drift_id: str) -> str:
    """Deterministic 20-character pseudo-LEI for a demo customer (offline only).

    NOT a registered LEI — a stable synthetic identifier so the seeded GLEIF
    baseline carries an own-LEI for the ownership-diff ``source_url`` and graph
    node identity. Derived from ``drift_id`` (SHA-1) so it is stable across
    restarts. ``DEMO`` prefix + 16 hex chars = 20 alphanumeric chars, matching
    the LEI charset/length without ever colliding with a real registry code.
    """
    # usedforsecurity=False: this is a stable demo identifier, not a security
    # hash — the flag also keeps it working under FIPS-restricted builds.
    digest = hashlib.sha1(drift_id.encode(), usedforsecurity=False).hexdigest().upper()
    return f"DEMO{digest[:16]}"


async def _seed_kyc_baselines(session: AsyncSession) -> None:
    """
    Populate entity_snapshots from the synthetic drift book.

    For each customer we capture a single 'seeded' onboarding snapshot whose
    behavioral baseline is computed from the pre-drift window (months before
    drift_start_month). Stable customers (drift_start_month is None) use the
    full history. This gives source adapters something real to diff against.
    """
    book = generate_book()
    snapshot_date = date(2023, 1, 1)  # synthetic onboarding date for the demo book

    for customer in book:
        # Use `is not None` to guard correctly: drift_start_month == 0 is falsy
        # but valid — using `or` would silently fall back to the full series.
        if customer.drift_start_month is not None:
            cutoff = customer.drift_start_month
        else:
            cutoff = len(customer.monthly_volume)

        baseline_volumes = customer.monthly_volume[:cutoff]
        baseline_cp = customer.counterparty_risk[:cutoff]
        baseline_cr = customer.corridor_risk[:cutoff]
        baseline_margin = customer.margin_ratio[:cutoff]

        legal_form = (
            "AG" if "AG" in customer.name or "Holdings" in customer.name else None
        )

        raw: dict = {
            "scenario": customer.scenario,
            "months": customer.months,
            "drift_start_month": customer.drift_start_month,
            "sanctions_month": customer.sanctions_month,
            "causal_truth": customer.causal_truth,
        }
        # Persist domain and sanctioned UBO name when set on the customer object,
        # so the live business-model comparison (UC9) and UBO screening (UC8) can
        # read them back from the snapshot without re-deriving from the name slug.
        if getattr(customer, "domain", None):
            raw["domain"] = customer.domain
        if getattr(customer, "sanctioned_ubo_name", None):
            raw["sanctioned_ubo_name"] = customer.sanctioned_ubo_name

        snapshot = EntitySnapshotDB(
            drift_id=customer.drift_id,
            snapshot_date=snapshot_date,
            snapshot_type="seeded",
            source="internal",
            name=customer.name,
            legal_form=legal_form,
            jurisdiction="CH",
            dissolution_status="active",
            beneficial_owners=[],
            officers=[],
            avg_monthly_volume_chf=_mean_of_windows(baseline_volumes),
            counterparty_risk_mean=_mean_of_windows(baseline_cp),
            corridor_risk_mean=_mean_of_windows(baseline_cr),
            margin_ratio_mean=_mean_of_windows(baseline_margin),
            raw_data=raw,
        )
        await store_snapshot(session, snapshot, flush=False)

        # GLEIF-source onboarding baseline (use case 3). The drift engine diffs
        # the *current* live GLEIF ownership chain against this same-source
        # anchor; the internal baseline above is excluded by that same-source
        # contract, which is why a dedicated gleif row is required for the
        # ownership_change diff to fire (PR #45 follow-up). It carries only the
        # registry/ownership fields (own LEI, empty onboarding parent/child
        # chain) — no behavioral columns and no "scenario" key, so it never
        # perturbs the behavioral baseline that ``load_all_baselines`` returns.
        # Its created_at is pinned 1s before the internal row so the internal
        # (behavioral) snapshot remains the latest-per-customer baseline.
        gleif_snapshot = EntitySnapshotDB(
            drift_id=customer.drift_id,
            snapshot_date=snapshot_date,
            snapshot_type="seeded",
            source="gleif",
            name=customer.name,
            legal_form=legal_form,
            jurisdiction="CH",
            dissolution_status="active",
            beneficial_owners=[],
            officers=[],
            raw_data={"lei": _synthetic_lei(customer.drift_id)},
            created_at=snapshot.created_at - timedelta(seconds=1),
        )
        await store_snapshot(session, gleif_snapshot, flush=False)

    logger.info("kyc_baselines_seeded", count=len(book))
