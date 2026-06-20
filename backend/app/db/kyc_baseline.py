"""
KYC baseline storage — EntitySnapshot per customer.

An EntitySnapshot is an immutable point-in-time record of a customer's KYC
profile: legal identity, ownership structure, financial profile, and
behavioral baseline. Source adapters (ZEFIX, GLEIF, OpenCorporates, …) will
produce new snapshots whenever they detect a change; the drift engine diffs the
latest snapshot against the onboarding snapshot to detect structural drift.

Design:
- One row per customer per snapshot event (history preserved, nothing deleted).
- `snapshot_type` distinguishes onboarding captures from periodic reviews.
- `source` records where the data came from so the diff layer can weight it.
- Behavioral baseline fields (volume, counterparty/corridor risk, margin) are
  aggregated from the first window of transaction data at onboarding time; they
  give the drift engine a numeric anchor to compare against current state.
- `raw_data` holds anything source-specific that doesn't fit the normalized
  columns; adapters dump their full payload here so nothing is lost.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Index, JSON, Column, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel, select

from app.core.logging import get_logger

logger = get_logger(__name__)

# Valid snapshot_type values (enforced by CheckConstraint below)
_VALID_SNAPSHOT_TYPES = ("onboarding", "annual_review", "triggered", "seeded")

# Valid source values (enforced by CheckConstraint below)
_VALID_SOURCES = (
    "internal", "zefix", "gleif", "open_corporates",
    "opensanctions", "event_registry", "crunchbase",
    "firecrawl", "wayback", "whois",
)


class EntitySnapshotDB(SQLModel, table=True):
    """
    Point-in-time KYC snapshot for one customer.

    Composite index on (customer_id, created_at) makes both common reads —
    "latest snapshot" and "onboarding baseline" — index-only range scans.

    Append-only: snapshots are never updated or deleted. When a source adapter
    detects a change it inserts a new row; the diff is implicit in the history.
    """

    __tablename__ = "entity_snapshots"
    __table_args__ = (
        # Composite index covers the two most common access patterns:
        #   load_latest_snapshot  → ORDER BY created_at DESC LIMIT 1
        #   load_onboarding_snapshot → WHERE snapshot_type = 'onboarding' ORDER BY created_at ASC
        Index("ix_entity_snapshots_customer_created", "customer_id", "created_at"),
        CheckConstraint(
            f"snapshot_type IN {_VALID_SNAPSHOT_TYPES}",
            name="ck_entity_snapshots_snapshot_type",
        ),
        CheckConstraint(
            f"source IN {_VALID_SOURCES}",
            name="ck_entity_snapshots_source",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # The drift engine uses string IDs ("drift-001") for synthetic customers;
    # the case-management system uses UUID strings for ClientDB rows.
    # We store both as strings so this table works for both.
    customer_id: str

    # When this snapshot was taken and what triggered it
    snapshot_date: date
    # One of _VALID_SNAPSHOT_TYPES — enforced by CheckConstraint
    snapshot_type: str = "onboarding"

    # Which external (or internal) system produced this snapshot
    # One of _VALID_SOURCES — enforced by CheckConstraint
    source: str = "internal"

    # === Legal identity ===
    name: str
    # Legal form uses free-text so adapters aren't constrained to a fixed enum.
    # Examples: "AG", "GmbH", "Ltd", "LLC", "individual", "foundation"
    legal_form: str | None = None
    jurisdiction: str | None = Field(
        default=None, description="ISO 3166-1 alpha-2 country of registration"
    )
    registered_address: str | None = None
    dissolution_status: str | None = Field(
        default=None, description="active | dissolved | dormant | struck_off"
    )

    # === Ownership & control ===
    # Stored as JSON lists of free-text names / LEI codes / UUID strings.
    # The contagion layer will eventually link these to graph nodes.
    beneficial_owners: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    officers: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )

    # === Financial & compliance profile ===
    risk_tolerance: str | None = None
    aum_chf: float | None = None
    is_pep: bool = False
    sanctions_check_passed: bool = True

    # === Behavioral baseline ===
    # Aggregated from the onboarding transaction window (first N months of data).
    # The drift engine compares current stats against these anchors.
    avg_monthly_volume_chf: float | None = Field(
        default=None,
        description="Mean monthly transaction volume at baseline (CHF)",
    )
    counterparty_risk_mean: float | None = Field(
        default=None,
        description="Mean counterparty risk score 0-1 at baseline",
    )
    corridor_risk_mean: float | None = Field(
        default=None,
        description="Mean payment corridor risk score 0-1 at baseline",
    )
    margin_ratio_mean: float | None = Field(
        default=None,
        description="Mean margin ratio 0-1 at baseline (causal discriminator)",
    )

    # === Raw source payload ===
    # Full adapter response; nothing is discarded. Structure varies per source.
    raw_data: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def store_snapshot(
    session: AsyncSession,
    snapshot: EntitySnapshotDB,
    *,
    flush: bool = False,
) -> EntitySnapshotDB:
    """
    Persist a new EntitySnapshot. Never updates an existing row.

    Set `flush=True` when you need the row immediately visible within the
    same transaction (e.g. during seeding before a final commit).
    """
    session.add(snapshot)
    if flush:
        await session.flush()
        logger.info(
            "entity_snapshot_stored",
            customer_id=snapshot.customer_id,
            snapshot_type=snapshot.snapshot_type,
            source=snapshot.source,
            snapshot_date=str(snapshot.snapshot_date),
        )
    return snapshot


async def load_latest_snapshot(
    session: AsyncSession,
    customer_id: str,
) -> EntitySnapshotDB | None:
    """
    Return the most recently created snapshot for `customer_id`, or None.

    'Most recent' is determined by `created_at` (wall-clock insertion order),
    not by `snapshot_date`. This means an out-of-order back-fill won't
    accidentally become the 'latest' anchor.
    """
    result = await session.execute(
        select(EntitySnapshotDB)
        .where(EntitySnapshotDB.customer_id == customer_id)
        .order_by(EntitySnapshotDB.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_onboarding_snapshot(
    session: AsyncSession,
    customer_id: str,
) -> EntitySnapshotDB | None:
    """
    Return the oldest baseline snapshot for `customer_id`, or None.

    Matches both 'onboarding' (real adapter) and 'seeded' (synthetic demo)
    types, as both represent the initial KYC reference point the drift engine
    diffs against. The oldest row is returned so re-KYC snapshots don't
    displace the original onboarding anchor.
    """
    result = await session.execute(
        select(EntitySnapshotDB)
        .where(
            EntitySnapshotDB.customer_id == customer_id,
            EntitySnapshotDB.snapshot_type.in_(("onboarding", "seeded")),
        )
        .order_by(EntitySnapshotDB.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_snapshot_history(
    session: AsyncSession,
    customer_id: str,
) -> list[EntitySnapshotDB]:
    """
    Return all snapshots for `customer_id`, newest-first.

    Used by the diff layer to build a change timeline and by the time-travel
    audit to verify that only data available at each point was used.
    """
    result = await session.execute(
        select(EntitySnapshotDB)
        .where(EntitySnapshotDB.customer_id == customer_id)
        .order_by(EntitySnapshotDB.created_at.desc())
    )
    return list(result.scalars().all())


async def load_all_baselines(
    session: AsyncSession,
) -> dict[str, EntitySnapshotDB]:
    """
    Return a mapping of customer_id → latest EntitySnapshot for every customer
    that has at least one snapshot.

    Uses a SQL-side MAX(created_at) subquery so only the matching rows are
    transferred; no full-table scan in Python.
    """
    subq = (
        select(
            EntitySnapshotDB.customer_id,
            func.max(EntitySnapshotDB.created_at).label("max_ts"),
        )
        .group_by(EntitySnapshotDB.customer_id)
        .subquery()
    )
    result = await session.execute(
        select(EntitySnapshotDB).join(
            subq,
            (EntitySnapshotDB.customer_id == subq.c.customer_id)
            & (EntitySnapshotDB.created_at == subq.c.max_ts),
        )
    )
    return {row.customer_id: row for row in result.scalars().all()}
