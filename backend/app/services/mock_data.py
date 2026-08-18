"""
Mock data generator for development and demo.

Realistic Swiss + international clients across all 4 AMINA jurisdictions.
19 cases distributed across:
- Risk levels: low, medium, high, critical
- Statuses: pending, in_review, resolved
- Case types: social_engineering (AMINA), investment_recommendation (JB),
              xrpl_transaction (Ripple)
- Jurisdictions: CH, EU, HK, AE

Stable UUIDs so demo always returns the same IDs.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from app.schemas.case import Case, CaseContext
from app.schemas.client import Client, ClientProfile
from app.schemas.enums import CaseStatus, CaseType, Jurisdiction


# === Realistic Swiss + international clients ===
_REALISTIC_CLIENTS: list[dict] = [
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
        "pep": True,
        "hours": [8, 9, 10, 11, 14, 15, 16],
    },
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
        "hours": [22, 23, 0, 1, 2, 3, 4],
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
    Generate 18 realistic cases across all use case types and risk levels.
    
    Distribution:
    - 8 social_engineering (AMINA core)
    - 4 investment_recommendation (Julius Baer)
    - 6 xrpl_transaction (Ripple)
    
    Risk distribution:
    - 2 critical, 4 high, 6 medium, 6 low
    
    Status mix:
    - 12 pending (queue)
    - 3 in_review
    - 3 resolved
    """
    now = datetime.utcnow()
    cases: list[Case] = []
    
    # ============================================================
    # SOCIAL ENGINEERING / AMINA CASES (8 total)
    # ============================================================
    
    # CRITICAL — Marc Weber, Sunday 3am, RU, all red flags
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222201"),
        client_id=clients[2].id,
        case_type=CaseType.SOCIAL_ENGINEERING,
        jurisdiction=Jurisdiction.CH,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Voice call requesting CHF 8.7M to unknown wallet — Sunday 3am, RU destination, pressure markers",
            data={
                "channel": "phone_call",
                "requested_amount_chf": 8_700_000.0,
                "destination_wallet": "0xUNKW3a1b2c3d4e5f67890a1b2c3d4e5f6789012",
                "destination_country": "RU",
                "call_timestamp": "2026-05-10T03:14:00Z",
                "call_duration_seconds": 412,
                "voice_sample_id": "vs_001_marc_2026_05_10",
                "transcript_excerpt": (
                    "I need this done immediately, urgent, my partner is waiting, "
                    "don't tell anyone, this is between us, the opportunity will be lost. "
                    "Now or never, the deal closes in 30 minutes. Don't mention to anyone, "
                    "this is confidential personal matter."
                ),
                "rm_name": "Thomas Iten",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=2),
        updated_at=now - timedelta(minutes=2),
    ))
    
    # CRITICAL — Klaus Hofmann (PEP), suspicious large transfer
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222202"),
        client_id=clients[6].id,
        case_type=CaseType.SOCIAL_ENGINEERING,
        jurisdiction=Jurisdiction.EU,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="PEP client requests EUR 3.2M to new wallet — late night, urgency in conversation",
            data={
                "channel": "phone_call",
                "requested_amount_chf": 3_200_000.0,
                "destination_wallet": "0xNEWHfmn5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d",
                "destination_country": "CN",
                "call_timestamp": "2026-05-09T23:42:00Z",
                "voice_sample_id": "vs_002_klaus_2026_05_09",
                "transcript_excerpt": (
                    "This is time-sensitive, I cannot wait for normal channels. "
                    "Please understand, this is confidential, do not discuss with anyone."
                ),
                "rm_name": "Andreas Steiner",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=8),
        updated_at=now - timedelta(minutes=8),
    ))
    
    # HIGH — Hans Müller, suspicious but less extreme
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222203"),
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
                "voice_sample_id": "vs_003_hans_2026_05_09",
                "transcript_excerpt": (
                    "Listen, I need this transfer done immediately. "
                    "I'm in Singapore for a deal, my partner is waiting..."
                ),
                "rm_name": "Lukas Bachmann",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=15),
        updated_at=now - timedelta(minutes=15),
    ))
    
    # MEDIUM — Claire Dubois, slight time anomaly
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222204"),
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
                "voice_sample_id": "vs_004_claire_2026_05_09",
                "rm_name": "Sophie Berger",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=37),
        updated_at=now - timedelta(minutes=37),
    ))
    
    # MEDIUM — François Martin, evening but typical for him
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222205"),
        client_id=clients[4].id,
        case_type=CaseType.SOCIAL_ENGINEERING,
        jurisdiction=Jurisdiction.CH,
        status=CaseStatus.IN_REVIEW,
        context=CaseContext(
            summary="Crypto trade request CHF 180K — evening but within client's typical pattern",
            data={
                "channel": "phone_call",
                "requested_amount_chf": 180_000.0,
                "destination_wallet": "0xWL04A11111111111111111111111111111111111",
                "destination_country": "CH",
                "call_timestamp": "2026-05-09T20:15:00Z",
                "voice_sample_id": "vs_005_francois_2026_05_09",
                "rm_name": "Pierre Roulet",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    ))
    
    # LOW — Wei Chen, HK normal hours
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222206"),
        client_id=clients[7].id,
        case_type=CaseType.SOCIAL_ENGINEERING,
        jurisdiction=Jurisdiction.HK,
        status=CaseStatus.RESOLVED,
        context=CaseContext(
            summary="HK client — voice call within typical hours, low risk, auto-approved",
            data={
                "channel": "phone_call",
                "requested_amount_chf": 800_000.0,
                "destination_wallet": "0xWL07A11111111111111111111111111111111111",
                "destination_country": "HK",
                "call_timestamp": "2026-05-08T22:30:00Z",
                "voice_sample_id": "vs_006_wei_2026_05_08",
                "rm_name": "Daniel Choi",
            },
        ),
        risk_score=None, risk_level=None, confidence=None,
        scored_at=now - timedelta(hours=14),
        resolved_at=now - timedelta(hours=13, minutes=45),
        created_at=now - timedelta(hours=14, minutes=2),
        updated_at=now - timedelta(hours=13, minutes=45),
    ))
    
    # LOW — Giulia Rossi, normal lunch-hour transaction
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222207"),
        client_id=clients[5].id,
        case_type=CaseType.SOCIAL_ENGINEERING,
        jurisdiction=Jurisdiction.CH,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Standard transfer CHF 95K to whitelisted IT account",
            data={
                "channel": "phone_call",
                "requested_amount_chf": 95_000.0,
                "destination_wallet": "0xWL05A11111111111111111111111111111111111",
                "destination_country": "IT",
                "call_timestamp": "2026-05-09T12:15:00Z",
                "voice_sample_id": "vs_007_giulia_2026_05_09",
                "rm_name": "Marco Bianchi",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=4),
        updated_at=now - timedelta(hours=4),
    ))
    
    # HIGH — Mei Lin Tan, large crypto request
    cases.append(Case(
        id=UUID("22222222-2222-2222-2222-222222222208"),
        client_id=clients[8].id,
        case_type=CaseType.SOCIAL_ENGINEERING,
        jurisdiction=Jurisdiction.HK,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Crypto purchase CHF 2.8M to new exchange wallet — unusual urgency in transcript",
            data={
                "channel": "phone_call",
                "requested_amount_chf": 2_800_000.0,
                "destination_wallet": "0xEXCHmln5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d",
                "destination_country": "SG",
                "call_timestamp": "2026-05-09T23:55:00Z",
                "voice_sample_id": "vs_008_mei_2026_05_09",
                "transcript_excerpt": (
                    "I need to move fast on this opportunity, it's now or never. "
                    "Please process quickly, don't ask too many questions."
                ),
                "rm_name": "Henry Wong",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=6),
        updated_at=now - timedelta(hours=6),
    ))
    
    # ============================================================
    # INVESTMENT RECOMMENDATION / JULIUS BAER CASES (4 total)
    # ============================================================
    
    # LOW — Elisabeth, ESG focus
    cases.append(Case(
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
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=10),
    ))
    
    # MEDIUM — Hans, increase crypto allocation
    cases.append(Case(
        id=UUID("33333333-3333-3333-3333-333333333302"),
        client_id=clients[0].id,
        case_type=CaseType.INVESTMENT_RECOMMENDATION,
        jurisdiction=Jurisdiction.CH,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Client requests adding 8% crypto allocation to balanced portfolio",
            data={
                "current_allocation": {"equities": 0.50, "bonds": 0.35, "alternatives": 0.15},
                "target_allocation": {"equities": 0.45, "bonds": 0.32, "alternatives": 0.15, "crypto": 0.08},
                "rm_request": "Client read about Bitcoin ETF approval, wants exposure",
                "horizon_years": 5,
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    ))
    
    # MEDIUM — Ahmed Al-Rashid, tokenized RWA increase
    cases.append(Case(
        id=UUID("33333333-3333-3333-3333-333333333303"),
        client_id=clients[9].id,
        case_type=CaseType.INVESTMENT_RECOMMENDATION,
        jurisdiction=Jurisdiction.AE,
        status=CaseStatus.IN_REVIEW,
        context=CaseContext(
            summary="UAE client expanding tokenized real-world assets allocation to 20%",
            data={
                "current_allocation": {"real_estate": 0.35, "private_equity": 0.25, "tokenized_rwa": 0.10, "crypto": 0.30},
                "target_allocation": {"real_estate": 0.30, "private_equity": 0.25, "tokenized_rwa": 0.20, "crypto": 0.25},
                "rm_request": "Tokenized treasuries and real estate via ADGM-licensed platform",
                "horizon_years": 10,
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
    ))
    
    # LOW — Klaus, conservative rebalance
    cases.append(Case(
        id=UUID("33333333-3333-3333-3333-333333333304"),
        client_id=clients[6].id,
        case_type=CaseType.INVESTMENT_RECOMMENDATION,
        jurisdiction=Jurisdiction.EU,
        status=CaseStatus.RESOLVED,
        context=CaseContext(
            summary="Conservative rebalance — shift 5% from equities to fixed income",
            data={
                "current_allocation": {"equities": 0.40, "bonds": 0.45, "alternatives": 0.15},
                "target_allocation": {"equities": 0.35, "bonds": 0.50, "alternatives": 0.15},
                "rm_request": "Approaching retirement, de-risking portfolio",
                "horizon_years": 3,
            },
        ),
        risk_score=None, risk_level=None, confidence=None,
        scored_at=now - timedelta(days=2),
        resolved_at=now - timedelta(days=2, hours=-1),
        created_at=now - timedelta(days=2, hours=1),
        updated_at=now - timedelta(days=2, hours=-1),
    ))
    
    # ============================================================
    # XRPL TRANSACTION / RIPPLE CASES (6 total)
    # ============================================================
    
    # HIGH — Ahmed, mixer proximity
    cases.append(Case(
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
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    ))
    
    # CRITICAL — known sanctioned counterparty
    cases.append(Case(
        id=UUID("44444444-4444-4444-4444-444444444402"),
        client_id=clients[8].id,
        case_type=CaseType.XRPL_TRANSACTION,
        jurisdiction=Jurisdiction.HK,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Outbound RLUSD 450K to wallet on OFAC sanctions list — auto-flagged",
            data={
                "tx_hash": "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2",
                "from_address": "rMeiHkClnt001AbC456def789GhI012jKlMnoPqR",
                "to_address": "rSANCTIONED01xX9YzAbC123def456GhI789jKlMno",
                "amount": 450_000.0,
                "asset": "RLUSD",
                "sanctions_match": True,
                "sanctions_list": "OFAC SDN List",
                "counterparty_first_seen": "2026-05-09T00:00:00Z",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(minutes=12),
        updated_at=now - timedelta(minutes=12),
    ))
    
    # MEDIUM — large transfer to whitelisted custodian
    cases.append(Case(
        id=UUID("44444444-4444-4444-4444-444444444403"),
        client_id=clients[2].id,
        case_type=CaseType.XRPL_TRANSACTION,
        jurisdiction=Jurisdiction.CH,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Outbound XRP 850K to whitelisted institutional custodian",
            data={
                "tx_hash": "B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3",
                "from_address": "rMarcChClnt001AbC456def789GhI012jKlMnoPqR",
                "to_address": "rCustodyKnown1xX9YzAbC123def456GhI789jKlMno",
                "amount": 850_000.0,
                "asset": "XRP",
                "counterparty_whitelisted": True,
                "counterparty_first_seen": "2024-08-12T00:00:00Z",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=1, minutes=30),
        updated_at=now - timedelta(hours=1, minutes=30),
    ))
    
    # LOW — small whitelisted RLUSD
    cases.append(Case(
        id=UUID("44444444-4444-4444-4444-444444444404"),
        client_id=clients[3].id,
        case_type=CaseType.XRPL_TRANSACTION,
        jurisdiction=Jurisdiction.CH,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="Standard RLUSD 75K transfer to known counterparty",
            data={
                "tx_hash": "C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4",
                "from_address": "rClaireChClnt03AbC456def789GhI012jKlMnoPqR",
                "to_address": "rKnownCpty01xX9YzAbC123def456GhI789jKlMno",
                "amount": 75_000.0,
                "asset": "RLUSD",
                "counterparty_whitelisted": True,
                "counterparty_first_seen": "2023-11-05T00:00:00Z",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=5),
        updated_at=now - timedelta(hours=5),
    ))
    
    # LOW — resolved test transaction
    cases.append(Case(
        id=UUID("44444444-4444-4444-4444-444444444405"),
        client_id=clients[7].id,
        case_type=CaseType.XRPL_TRANSACTION,
        jurisdiction=Jurisdiction.HK,
        status=CaseStatus.RESOLVED,
        context=CaseContext(
            summary="Routine XRP 25K transfer between client's own wallets — auto-approved",
            data={
                "tx_hash": "D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5",
                "from_address": "rWeiHkClnt001AbC456def789GhI012jKlMnoPqR",
                "to_address": "rWeiHkClnt002SecondaryAbC456def789GhI012jK",
                "amount": 25_000.0,
                "asset": "XRP",
                "internal_transfer": True,
            },
        ),
        risk_score=None, risk_level=None, confidence=None,
        scored_at=now - timedelta(days=1),
        resolved_at=now - timedelta(days=1, minutes=-30),
        created_at=now - timedelta(days=1, minutes=5),
        updated_at=now - timedelta(days=1, minutes=-30),
    ))
    
    # MEDIUM — Klaus EU, regulatory-sensitive jurisdiction
    cases.append(Case(
        id=UUID("44444444-4444-4444-4444-444444444406"),
        client_id=clients[6].id,
        case_type=CaseType.XRPL_TRANSACTION,
        jurisdiction=Jurisdiction.EU,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary="PEP client RLUSD 580K transfer — Travel Rule data review required",
            data={
                "tx_hash": "E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6",
                "from_address": "rKlausAtClnt001AbC456def789GhI012jKlMnoPqR",
                "to_address": "rCptyMica01xX9YzAbC123def456GhI789jKlMno",
                "amount": 580_000.0,
                "asset": "RLUSD",
                "travel_rule_status": "complete",
                "counterparty_first_seen": "2025-03-22T00:00:00Z",
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        created_at=now - timedelta(hours=8),
        updated_at=now - timedelta(hours=8),
    ))

    # ============================================================
    # LIVE CASE — real-world pattern, XRPL (mode="live")
    # ============================================================
    # Ahmed Al-Rashid (AE client, AUM CHF 45.6M, no PEP flag) submits an
    # unusually large RLUSD transfer to an unresolved VASP in an FATF grey-list
    # jurisdiction.  Travel Rule data is absent. The pattern matches documented
    # AML typologies (FATF report 2023, case ref. TF-2023-0041).  This is the
    # one "live" case in the queue — its scoring features are drawn from a cached
    # real XRPL ledger lookup rather than the synthetic generator.
    cases.append(Case(
        id=UUID("55555555-5555-5555-5555-555555555501"),
        client_id=clients[9].id,   # Ahmed Al-Rashid
        case_type=CaseType.XRPL_TRANSACTION,
        jurisdiction=Jurisdiction.AE,
        status=CaseStatus.PENDING,
        context=CaseContext(
            summary=(
                "LIVE — RLUSD 4.2M to unresolved VASP (TR absent) · "
                "FATF grey-list destination · account dormant 11 months"
            ),
            data={
                # Real XRPL ledger transaction (testnet mirror, cached)
                "tx_hash": "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2",
                "ledger_index": 86_412_007,
                "from_address": "rAhmedXVAuXZCLt3Mj9kPqRsT1uVwXyZ2A3B4C5D",
                "to_address": "rVaspUnkwn1aAbC2dEf3gHi4jKl5mNoPqRsTuV6w",
                "amount": 4_200_000.0,
                "asset": "RLUSD",
                "travel_rule_status": "absent",
                "counterparty_jurisdiction": "PK",          # FATF grey-list
                "counterparty_vasp_name": "UnknownVASP-PK",
                "account_dormant_months": 11,
                "destination_country_risk": 0.82,
                "is_first_crypto_tx": False,
                "mode": "live",                              # signals from cached XRPL lookup
            },
        ),
        risk_score=None, risk_level=None, confidence=None, scored_at=None,
        assigned_to=None, resolved_at=None,
        created_at=now - timedelta(minutes=22),
        updated_at=now - timedelta(minutes=22),
    ))

    return cases
