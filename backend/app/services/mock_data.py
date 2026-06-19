"""
Mock data generator for development and demo.

Why realistic data matters:
- Demo with "client_001, $1000" looks amateur
- Demo with "Hans Müller, CHF 4.7M, Zürich" looks like a real product
- Names span CH (DE/FR/IT), EU, HK, AE jurisdictions

This module is the SINGLE SOURCE OF TRUTH for demo data.
Day 11 we'll replace this with a more sophisticated faker-based generator.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from app.schemas.case import Case, CaseContext
from app.schemas.client import Client, ClientProfile
from app.schemas.enums import CaseStatus, CaseType, Jurisdiction


# === Realistic Swiss + international names ===
# Mix of German-speaking CH, French-speaking CH, Italian-speaking CH, EU, APAC, MENA
_REALISTIC_CLIENTS: list[dict] = [
    # Swiss German clients (Zurich, Bern, Basel)
    {
        "name": "Hans Müller",
        "email": "h.mueller@example.ch",
        "dob": date(1965, 3, 12),
        "nationality": "CH",
        "residence": "CH",
        "jurisdiction": Jurisdiction.CH,
        "risk": "moderate",
        "aum": 12_500_000.0,
        "esg": True,
        "assets": ["equities", "bonds", "alternatives"],
        "pep": False,
        "hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    },
    {
        "name": "Elisabeth Schneider",
        "email": "e.schneider@example.ch",
        "dob": date(1972, 7, 28),
        "nationality": "CH",
        "residence": "CH",
        "jurisdiction": Jurisdiction.CH,
        "risk": "conservative",
        "aum": 4_800_000.0,
        "esg": True,
        "assets": ["bonds", "real_estate"],
        "pep": False,
        "hours": [9, 10, 11, 14, 15, 16],
    },
    {
        "name": "Marc Weber",
        "email": "m.weber@example.ch",
        "dob": date(1958, 11, 4),
        "nationality": "CH",
        "residence": "CH",
        "jurisdiction": Jurisdiction.CH,
        "risk": "growth",
        "aum": 28_300_000.0,
        "esg": False,
        "assets": ["equities", "crypto", "private_equity"],
        "pep": False,
        "hours": [7, 8, 9, 10, 18, 19, 20],
    },
    # Swiss French clients (Geneva, Lausanne)
    {
        "name": "Claire Dubois",
        "email": "c.dubois@example.ch",
        "dob": date(1968, 5, 17),
        "nationality": "CH",
        "residence": "CH",
        "jurisdiction": Jurisdiction.CH,
        "risk": "balanced",
        "aum": 15_700_000.0,
        "esg": True,
        "assets": ["equities", "bonds", "private_credit"],
        "pep": False,
        "hours": [9, 10, 11, 12, 14, 15, 16, 17],
    },
    {
        "name": "François Martin",
        "email": "f.martin@example.ch",
        "dob": date(1975, 2, 22),
        "nationality": "FR",
        "residence": "CH",
        "jurisdiction": Jurisdiction.CH,
        "risk": "aggressive",
        "aum": 8_900_000.0,
        "esg": False,
        "assets": ["crypto", "equities", "venture"],
        "pep": False,
        "hours": [10, 11, 14, 15, 16, 19, 20, 21],
    },
    # Italian Switzerland (Lugano)
    {
        "name": "Giulia Rossi",
        "email": "g.rossi@example.ch",
        "dob": date(1980, 9, 8),
        "nationality": "IT",
        "residence": "CH",
        "jurisdiction": Jurisdiction.CH,
        "risk": "moderate",
        "aum": 6_400_000.0,
        "esg": True,
        "assets": ["equities", "bonds"],
        "pep": False,
        "hours": [9, 10, 11, 14, 15, 16, 17],
    },
    # EU clients (MiCA jurisdiction via AMINA Austria)
    {
        "name": "Klaus Hofmann",
        "email": "k.hofmann@example.at",
        "dob": date(1962, 12, 1),
        "nationality": "AT",
        "residence": "AT",
        "jurisdiction": Jurisdiction.EU,
        "risk": "balanced",
        "aum": 19_200_000.0,
        "esg": True,
        "assets": ["bonds", "real_estate", "tokenized_rwa"],
        "pep": True,  # Former government official
        "hours": [8, 9, 10, 11, 14, 15, 16],
    },
    # Hong Kong (SFC jurisdiction)
    {
        "name": "Wei Chen",
        "email": "w.chen@example.hk",
        "dob": date(1970, 6, 30),
        "nationality": "HK",
        "residence": "HK",
        "jurisdiction": Jurisdiction.HK,
        "risk": "growth",
        "aum": 32_100_000.0,
        "esg": False,
        "assets": ["equities", "crypto", "structured_products"],
        "pep": False,
        "hours": [22, 23, 0, 1, 2, 3, 4],  # HK timezone activity
    },
    {
        "name": "Mei Lin Tan",
        "email": "m.tan@example.hk",
        "dob": date(1985, 4, 18),
        "nationality": "SG",
        "residence": "HK",
        "jurisdiction": Jurisdiction.HK,
        "risk": "aggressive",
        "aum": 11_800_000.0,
        "esg": False,
        "assets": ["crypto", "venture", "tokenized_rwa"],
        "pep": False,
        "hours": [21, 22, 23, 0, 1, 2],
    },
    # UAE / ADGM (FSRA jurisdiction)
    {
        "name": "Ahmed Al-Rashid",
        "email": "a.alrashid@example.ae",
        "dob": date(1973, 8, 14),
        "nationality": "AE",
        "residence": "AE",
        "jurisdiction": Jurisdiction.AE,
        "risk": "balanced",
        "aum": 45_600_000.0,
        "esg": False,
        "assets": ["real_estate", "private_equity", "tokenized_rwa", "crypto"],
        "pep": False,
        "hours": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    },
]


# Stable UUIDs so demo always returns the same IDs (easier for testing)
_CLIENT_UUIDS = [
    UUID("11111111-1111-1111-1111-111111111101"),
    UUID("11111111-1111-1111-1111-111111111102"),
    UUID("11111111-1111-1111-1111-111111111103"),
    UUID("11111111-1111-1111-1111-111111111104"),
    UUID("11111111-1111-1111-1111-111111111105"),
    UUID("11111111-1111-1111-1111-111111111106"),
    UUID("11111111-1111-1111-1111-111111111107"),
    UUID("11111111-1111-1111-1111-111111111108"),
    UUID("11111111-1111-1111-1111-111111111109"),
    UUID("11111111-1111-1111-1111-11111111110a"),
]


def generate_mock_clients() -> list[Client]:
    """Create 10 realistic clients spanning all jurisdictions."""
    
    base_onboard = date(2022, 1, 1)
    clients: list[Client] = []
    
    for idx, (raw, uid) in enumerate(zip(_REALISTIC_CLIENTS, _CLIENT_UUIDS, strict=True)):
        profile = ClientProfile(
            full_name=raw["name"],
            email=raw["email"],
            date_of_birth=raw["dob"],
            nationality=raw["nationality"],
            residence_country=raw["residence"],
            primary_jurisdiction=raw["jurisdiction"],
            onboarded_at=base_onboard + timedelta(days=idx * 137),
            risk_tolerance=raw["risk"],
            aum_chf=raw["aum"],
            esg_focus=raw["esg"],
            preferred_asset_classes=raw["assets"],
            is_pep=raw["pep"],
            sanctions_check_passed=True,
            last_review_date=date(2026, 1, 15) - timedelta(days=idx * 7),
            typical_transaction_hours=raw["hours"],
            typical_transaction_currency="CHF" if raw["jurisdiction"] == Jurisdiction.CH else "USD",
            whitelist_wallets=[
                f"0xWL{idx:02d}A{'1' * 32}",
                f"0xWL{idx:02d}B{'2' * 32}",
            ],
        )
        
        clients.append(
            Client(
                id=uid,
                profile=profile,
                created_at=datetime(2022, 1, 1) + timedelta(days=idx * 137),
                updated_at=datetime(2026, 1, 15) - timedelta(days=idx * 7),
            )
        )
    
    return clients


def generate_mock_cases(clients: list[Client]) -> list[Case]:
    """
    Generate realistic cases across all use case types.
    Mix of pending / resolved with realistic risk scores.
    """
    
    now = datetime.utcnow()
    cases: list[Case] = []
    
    # === AMINA: Social engineering case (high risk, pending) ===
    # Hans Müller: typical CH client, but suspicious Saturday evening call
    cases.append(
        Case(
            id=UUID("22222222-2222-2222-2222-222222222201"),
            client_id=clients[0].id,
            case_type=CaseType.SOCIAL_ENGINEERING,
            jurisdiction=Jurisdiction.CH,
            status=CaseStatus.PENDING,
            context=CaseContext(
                summary="Voice call requesting CHF 4.5M transfer to new wallet — outside business hours",
                data={
                    "channel": "phone_call",
                    "requested_amount_chf": 4_500_000.0,
                    "destination_wallet": "0xNEW7a3b9c2d1e8f4a6b5c7d9e1f2a3b4c5d6e7f8",
                    "destination_country": "SG",
                    "call_timestamp": "2026-05-09T20:47:00Z",
                    "call_duration_seconds": 187,
                    "voice_sample_id": "vs_001_hans_2026_05_09",
                    "transcript_excerpt": (
                        "Listen, I need this transfer done immediately. "
                        "I'm in Singapore for a deal, my partner is waiting..."
                    ),
                    "rm_name": "Lukas Bachmann",
                },
            ),
            risk_score=87.3,
            risk_level="critical",
            confidence=0.92,
            scored_at=now - timedelta(minutes=12),
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=12),
        )
    )
    
    # === AMINA: Lower-risk transaction (medium, pending) ===
    cases.append(
        Case(
            id=UUID("22222222-2222-2222-2222-222222222202"),
            client_id=clients[3].id,
            case_type=CaseType.SOCIAL_ENGINEERING,
            jurisdiction=Jurisdiction.CH,
            status=CaseStatus.PENDING,
            context=CaseContext(
                summary="Voice call requesting CHF 250K to whitelisted wallet — slight time anomaly",
                data={
                    "channel": "phone_call",
                    "requested_amount_chf": 250_000.0,
                    "destination_wallet": "0xWL03A11111111111111111111111111111111111",
                    "destination_country": "CH",
                    "call_timestamp": "2026-05-09T07:15:00Z",
                    "voice_sample_id": "vs_002_claire_2026_05_09",
                    "rm_name": "Sophie Berger",
                },
            ),
            risk_score=42.1,
            risk_level="medium",
            confidence=0.78,
            scored_at=now - timedelta(minutes=34),
            created_at=now - timedelta(minutes=37),
            updated_at=now - timedelta(minutes=34),
        )
    )
    
    # === AMINA: Resolved case for history view ===
    cases.append(
        Case(
            id=UUID("22222222-2222-2222-2222-222222222203"),
            client_id=clients[7].id,
            case_type=CaseType.SOCIAL_ENGINEERING,
            jurisdiction=Jurisdiction.HK,
            status=CaseStatus.RESOLVED,
            context=CaseContext(
                summary="HK client — voice call within typical hours, low risk, auto-approved",
                data={
                    "channel": "phone_call",
                    "requested_amount_chf": 800_000.0,
                    "voice_sample_id": "vs_003_wei_2026_05_08",
                    "rm_name": "Daniel Choi",
                },
            ),
            risk_score=18.5,
            risk_level="low",
            confidence=0.94,
            scored_at=now - timedelta(hours=14),
            resolved_at=now - timedelta(hours=13, minutes=45),
            created_at=now - timedelta(hours=14, minutes=2),
            updated_at=now - timedelta(hours=13, minutes=45),
        )
    )
    
    # === Julius Baer: Investment recommendation case ===
    cases.append(
        Case(
            id=UUID("33333333-3333-3333-3333-333333333301"),
            client_id=clients[1].id,
            case_type=CaseType.INVESTMENT_RECOMMENDATION,
            jurisdiction=Jurisdiction.CH,
            status=CaseStatus.PENDING,
            context=CaseContext(
                summary="Recommendation request: ESG-focused mid-cap equities allocation review",
                data={
                    "current_allocation": {"equities": 0.45, "bonds": 0.40, "alternatives": 0.15},
                    "target_allocation": {"equities": 0.55, "bonds": 0.30, "alternatives": 0.15},
                    "rm_request": "Client interested in increasing ESG exposure within EU equities",
                    "horizon_years": 7,
                },
            ),
            risk_score=23.0,
            risk_level="low",
            confidence=0.88,
            scored_at=now - timedelta(minutes=8),
            created_at=now - timedelta(minutes=10),
            updated_at=now - timedelta(minutes=8),
        )
    )
    
    # === Ripple: XRPL transaction AML case ===
    cases.append(
        Case(
            id=UUID("44444444-4444-4444-4444-444444444401"),
            client_id=clients[9].id,
            case_type=CaseType.XRPL_TRANSACTION,
            jurisdiction=Jurisdiction.AE,
            status=CaseStatus.PENDING,
            context=CaseContext(
                summary="Incoming RLUSD 1.2M from new counterparty wallet — mixer proximity flagged",
                data={
                    "tx_hash": "9F2A4B3C8E1D7F6A5B4C3D2E1F8A9B7C6D5E4F3A2B1C8D7E6F5A4B3C2D1E8F9A",
                    "from_address": "rNewCpty7x9YzAbC123def456GhI789jKlMnoPqR",
                    "to_address": "rAminaInst001AbC456def789GhI012jKlMnoPqR",
                    "amount": 1_200_000.0,
                    "asset": "RLUSD",
                    "mixer_proximity_hops": 2,
                    "counterparty_first_seen": "2026-04-18T00:00:00Z",
                },
            ),
            risk_score=71.4,
            risk_level="high",
            confidence=0.83,
            scored_at=now - timedelta(minutes=3),
            created_at=now - timedelta(minutes=5),
            updated_at=now - timedelta(minutes=3),
        )
    )
    
    return cases
