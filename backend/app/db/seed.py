"""
Database seeding — fills the freshly recreated DB with mock data at startup.

Uses the existing mock_data generators from services/mock_data.py.
Idempotent: only runs if DB is empty.
"""

from __future__ import annotations

from datetime import date

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
    Seed the DB with mock data if no clients exist.
    
    Returns True if seeding happened, False if skipped.
    """
    # Check if already seeded
    result = await session.execute(select(ClientDB).limit(1))
    if result.scalar_one_or_none() is not None:
        logger.info("seed_skipped", reason="already_populated")
        return False
    
    logger.info("seed_starting")
    
    # === Seed clients ===
    mock_clients = generate_mock_clients()
    for client in mock_clients:
        profile = client.profile
        
        # Pull dynamic profile fields into JSON column
        profile_data = {
            "date_of_birth": (
                profile.date_of_birth.isoformat()
                if profile.date_of_birth
                else None
            ),
            "preferred_asset_classes": profile.preferred_asset_classes,
            "typical_transaction_hours": profile.typical_transaction_hours,
            "typical_transaction_currency": profile.typical_transaction_currency,
            "whitelist_wallets": profile.whitelist_wallets,
        }
        
        client_db = ClientDB(
            id=client.id,
            full_name=profile.full_name,
            email=profile.email,
            nationality=profile.nationality,
            residence_country=profile.residence_country,
            primary_jurisdiction=profile.primary_jurisdiction,
            risk_tolerance=profile.risk_tolerance,
            aum_chf=profile.aum_chf,
            esg_focus=profile.esg_focus,
            is_pep=profile.is_pep,
            sanctions_check_passed=profile.sanctions_check_passed,
            onboarded_at=profile.onboarded_at,
            last_review_date=profile.last_review_date,
            profile_data=profile_data,
            created_at=client.created_at,
            updated_at=client.updated_at,
        )
        session.add(client_db)
    
    # Flush to make clients available for FK references
    await session.flush()
    
    # === Seed cases ===
    mock_cases = generate_mock_cases(mock_clients)
    for case in mock_cases:
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
    
    # === Seed KYC baselines from the synthetic drift book ===
    await _seed_kyc_baselines(session)

    await session.commit()

    logger.info(
        "seed_completed",
        client_count=len(mock_clients),
        case_count=len(mock_cases),
    )
    return True


def _mean_of_windows(windows: list) -> float | None:
    """Mean of per-window means. Returns None for an empty window list."""
    if not windows:
        return None
    return float(np.mean([w.mean() for w in windows]))


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

        snapshot = EntitySnapshotDB(
            customer_id=customer.customer_id,
            snapshot_date=snapshot_date,
            snapshot_type="seeded",
            source="internal",
            name=customer.name,
            legal_form="AG" if "AG" in customer.name or "Holdings" in customer.name else None,
            jurisdiction="CH",
            dissolution_status="active",
            beneficial_owners=[],
            officers=[],
            avg_monthly_volume_chf=_mean_of_windows(baseline_volumes),
            counterparty_risk_mean=_mean_of_windows(baseline_cp),
            corridor_risk_mean=_mean_of_windows(baseline_cr),
            margin_ratio_mean=_mean_of_windows(baseline_margin),
            raw_data={
                "scenario": customer.scenario,
                "months": customer.months,
                "drift_start_month": customer.drift_start_month,
                "sanctions_month": customer.sanctions_month,
                "causal_truth": customer.causal_truth,
            },
        )
        await store_snapshot(session, snapshot, flush=False)

    logger.info("kyc_baselines_seeded", count=len(book))
