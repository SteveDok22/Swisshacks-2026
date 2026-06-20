# Database Schema

## Entity Relationship Diagram

```mermaid
erDiagram
    CLIENT {
        uuid id PK
        string full_name
        string email
        string nationality
        string residence_country
        Jurisdiction primary_jurisdiction
        string risk_tolerance
        float aum_chf
        bool esg_focus
        bool is_pep
        bool sanctions_check_passed
        date onboarded_at
        date last_review_date
        json profile_data
        datetime created_at
        datetime updated_at
    }

    CASE {
        uuid id PK
        uuid client_id FK
        string case_type
        string jurisdiction
        string status
        string summary
        json context_data
        float risk_score
        string risk_level
        float confidence
        string assigned_to
        datetime created_at
        datetime updated_at
        datetime scored_at
        datetime resolved_at
    }

    DECISION {
        uuid id PK
        uuid case_id FK "nullable — null for drift decisions"
        string drift_id "nullable — set for drift-engine decisions"
        string action
        string officer_id
        string rationale
        bool overrode_ai
        string ai_recommended_action
        float ai_risk_score
        string ai_risk_level
        json analysis_snapshot
        datetime created_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid case_id FK
        uuid client_id FK
        string drift_id
        string event_type
        string actor_id
        string actor_type
        json payload
        float risk_score
        string risk_level
        datetime occurred_at
    }

    ENTITY_SNAPSHOT {
        uuid id PK
        string drift_id
        date snapshot_date
        string snapshot_type "onboarding|annual_review|triggered|seeded"
        string source "internal|zefix|gleif|open_corporates|..."
        string name
        string legal_form
        string jurisdiction
        string registered_address
        string dissolution_status
        json beneficial_owners
        json officers
        string risk_tolerance
        float aum_chf
        bool is_pep
        bool sanctions_check_passed
        float avg_monthly_volume_chf
        float counterparty_risk_mean
        float corridor_risk_mean
        float margin_ratio_mean
        json raw_data
        datetime created_at
    }

    CLIENT ||--o{ CASE : "has"
    CASE |o--o{ DECISION : "receives (nullable — drift decisions have no case)"
    CASE |o--o{ AUDIT_LOG : "soft ref"
    CLIENT |o--o{ AUDIT_LOG : "soft ref"
```

---

## Enumerations

```mermaid
flowchart LR
    subgraph RiskLevel["RiskLevel"]
        RL1["low\n0–30"]
        RL2["medium\n31–60"]
        RL3["high\n61–85"]
        RL4["critical\n86–100"]
    end

    subgraph CaseStatus["CaseStatus"]
        CS1[pending]
        CS2[in_review]
        CS3[resolved]
        CS4[expired]
    end

    subgraph DecisionAction["DecisionAction"]
        A1[allow]
        A2[step_up_verification]
        A3[escalate]
        A4[block]
    end

    subgraph CaseType["CaseType"]
        CT1[kyc_drift]
        CT2[social_engineering]
        CT3[portfolio_risk]
        CT4[investment_recommendation]
        CT5[client_onboarding]
        CT6[xrpl_transaction]
    end

    subgraph Jurisdiction["Jurisdiction"]
        J1["CH — FINMA"]
        J2["EU — MiCA"]
        J3["HK — SFC"]
        J4["AE — FSRA"]
    end
```

> Jurisdiction is stored as bare code: `"CH"`, `"EU"`, `"HK"`, `"AE"`.

---

## Decision Workflows

Two distinct decision paths share the same `decisions` table:

| Field | Case-review workflow | Drift-engine workflow |
|---|---|---|
| `case_id` | Set (UUID FK → cases) | `NULL` |
| `drift_id` | `NULL` | Set (drift customer string ID) |
| `ai_recommended_action` | Derived from `case.risk_score` thresholds | Derived by the backend from the current drift analysis |
| `analysis_snapshot` | Case type, jurisdiction, confidence | Score, risk level, tier, causal evidence, stability, and analysis version |
| Audit event type | `decision_recorded` | `drift_decision_recorded` |
| Case status updated | Yes (`resolved` / `in_review`) | No (no linked case record) |

Both paths enforce the same override rule: if `action ≠ ai_recommended_action`, a `rationale` of ≥ 10 characters is required.

The SQLite schema is disposable and is dropped/recreated on every backend
startup before mock data is seeded.

---

## EntitySnapshot — KYC Baseline Store

`entity_snapshots` is an **append-only** table that records the KYC profile of
a customer at a point in time. Source adapters (ZEFIX, GLEIF, OpenCorporates,
…) write a new row whenever they detect a registry change; the drift engine
diffs the current snapshot against the onboarding baseline to flag structural
drift (name change, legal form change, UBO change, etc.).

**Lookup patterns supported:**

| Query | Function |
|---|---|
| Latest snapshot for a customer | `load_latest_snapshot(session, drift_id)` |
| Onboarding baseline | `load_onboarding_snapshot(session, drift_id)` |
| Full change history | `load_snapshot_history(session, drift_id)` |
| Book-wide latest baselines | `load_all_baselines(session)` |

**Snapshot types:**

| Type | When written |
|---|---|
| `onboarding` | At KYC onboarding (real adapter) |
| `annual_review` | During periodic re-KYC |
| `triggered` | On event (sanctions hit, news spike, etc.) |
| `seeded` | Startup seed from synthetic book (demo) |

**Behavioral baseline fields** (`avg_monthly_volume_chf`, `counterparty_risk_mean`,
`corridor_risk_mean`, `margin_ratio_mean`) are computed from the pre-drift
transaction window at seeding time and serve as numeric anchors for the drift
velocity and causal layers.

---

## Data Flow: KYC Case Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: Case created\n(ingest or manual)
    pending --> in_review: Officer opens case
    pending --> expired: Timeout — no action taken
    in_review --> resolved: Officer logs decision\n(allow / step_up_verification / escalate / block)
    in_review --> expired: Timeout — abandoned
    resolved --> [*]: Audit record written\n(immutable)
    expired --> [*]: Audit record written\n(immutable)

    note right of resolved
        FINMA Circular 2024/3:
        human-in-the-loop required
        for all consequential actions.
        DecisionDB.overrode_ai records
        whether officer overrode AI.
    end note
```
