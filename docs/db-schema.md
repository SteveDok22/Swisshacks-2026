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
        string customer_id "nullable — set for drift-engine decisions"
        string action
        string officer_id
        string rationale
        bool overrode_ai
        string ai_recommended_action
        float ai_risk_score
        string ai_risk_level
        datetime created_at
    }

    AUDIT_LOG {
        uuid id PK
        uuid case_id FK
        uuid client_id FK
        string event_type
        string actor_id
        string actor_type
        json payload
        float risk_score
        string risk_level
        datetime occurred_at
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
| `customer_id` | `NULL` | Set (drift customer string ID) |
| `ai_recommended_action` | Derived from `case.risk_score` thresholds | Passed as `ai_hint` by the caller (VerdictBar logic) |
| Audit event type | `decision_recorded` | `drift_decision_recorded` |
| Case status updated | Yes (`resolved` / `in_review`) | No (no linked case record) |

Both paths enforce the same override rule: if `action ≠ ai_recommended_action`, a `rationale` of ≥ 10 characters is required.

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
