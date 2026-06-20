"""
Database seeding — fills the freshly recreated DB with mock data at startup.

Uses the existing mock_data generators from services/mock_data.py.
Idempotent: only runs if DB is empty.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import get_logger
from app.db.models import CaseDB, ClientDB
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
    
    await session.commit()
    
    logger.info(
        "seed_completed",
        client_count=len(mock_clients),
        case_count=len(mock_cases),
    )
    return True
