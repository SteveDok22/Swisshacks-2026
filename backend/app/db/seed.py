"""
Database seeding — two independent paths, both idempotent:

1. KYC baselines (entity_snapshots table): one snapshot per drift subject from
   the synthetic book. Used by the Drift Engine for source-level comparison.

2. Case Queue (clients + cases tables): 10 private-wealth clients and 18 cases
   (social engineering, investment recommendations, XRPL transactions) from
   mock_data.py. Used by the /cases workspace.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.db.kyc_baseline import EntitySnapshotDB, store_snapshot
from app.db.models import CaseDB, ClientDB
from app.drift.simulator import generate_book
from app.services.mock_data import generate_mock_cases, generate_mock_clients

logger = get_logger(__name__)


async def seed_if_empty(session: AsyncSession) -> bool:
    """
    Seed the database if either table is empty. Both paths are idempotent and
    independent — one can be populated without the other.

    Returns True if any seeding happened, False if both were already populated.
    """
    seeded = False

    # --- Path 1: KYC baselines for the Drift Engine ---
    snap_result = await session.execute(select(EntitySnapshotDB).limit(1))
    if snap_result.scalar_one_or_none() is None:
        logger.info("seed_starting", path="kyc_baselines")
        await _seed_kyc_baselines(session)
        seeded = True

    # --- Path 2: Case Queue (clients + cases) ---
    client_result = await session.execute(select(ClientDB).limit(1))
    if client_result.scalar_one_or_none() is None:
        logger.info("seed_starting", path="case_queue")
        await _seed_case_queue(session)
        seeded = True

    if seeded:
        await session.commit()
        logger.info("seed_completed")
    else:
        logger.info("seed_skipped", reason="already_populated")

    return seeded


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


async def _seed_case_queue(session: AsyncSession) -> None:
    """
    Seed the Case Queue with 10 private-wealth clients and 18 compliance cases
    (social engineering, investment recommendations, XRPL transactions).

    Converts mock_data.py domain objects to DB rows using the same field
    mapping as DbStore.add_case() / _client_db_to_domain().
    """
    clients = generate_mock_clients()

    for c in clients:
        p = c.profile
        client_db = ClientDB(
            id=c.id,
            full_name=p.full_name,
            email=p.email,
            nationality=p.nationality,
            residence_country=p.residence_country,
            primary_jurisdiction=p.primary_jurisdiction,
            risk_tolerance=p.risk_tolerance,
            aum_chf=p.aum_chf,
            esg_focus=p.esg_focus,
            is_pep=p.is_pep,
            sanctions_check_passed=p.sanctions_check_passed,
            onboarded_at=p.onboarded_at,
            last_review_date=p.last_review_date,
            profile_data={
                "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
                "preferred_asset_classes": p.preferred_asset_classes,
                "whitelist_wallets": p.whitelist_wallets,
                "typical_transaction_hours": p.typical_transaction_hours,
                "typical_transaction_currency": p.typical_transaction_currency,
            },
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        session.add(client_db)

    await session.flush()

    cases = generate_mock_cases(clients)
    for case in cases:
        case_db = CaseDB(
            id=case.id,
            client_id=case.client_id,
            case_type=case.case_type,
            jurisdiction=case.jurisdiction,
            status=case.status,
            summary=case.context.summary,
            context_data=case.context.data,
            risk_score=case.risk_score,
            risk_level=case.risk_level,
            confidence=case.confidence,
            assigned_to=case.assigned_to,
            created_at=case.created_at,
            updated_at=case.updated_at,
            scored_at=case.scored_at,
            resolved_at=case.resolved_at,
        )
        session.add(case_db)

    logger.info("case_queue_seeded", clients=len(clients), cases=len(cases))
