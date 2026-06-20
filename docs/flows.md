# User Flows & Use Cases

## Challenge Use Cases (from AMINA brief)

Ten specific signal scenarios the system must detect and action. See [CHALLENGE_4_OVERVIEW.md](CHALLENGE_4_OVERVIEW.md) for the full table.

```mermaid
flowchart TD
    subgraph Signals["Incoming Signals"]
        S1["Negative news spike\n→ High Reputational Risk"]
        S2["Cross-border transfers\ninconsistent with history\n→ Behavioural Anomaly"]
        S3["Multiple linked entities\n+ sudden large flows\n→ Structuring / Layering"]
        S4["Legal entity name change\n→ Re-KYC Required"]
        S5["Domain switch or\nwebsite content change\n→ Business Activity Change"]
        S6["Public pivot\n(SaaS → crypto)\n→ Business Model Change"]
        S7["Jurisdiction move\nor legal form change\n→ Structural Risk Change"]
        S8["New shareholders\nor beneficial owners\n→ Ownership KYC Drift"]
        S9["Large funding round\nor rapid expansion\n→ Scale Risk Change"]
        S10["Dormant company\nresumes high volume\n→ Suspicious Activation"]
    end

    Engine["Drift Engine\n7-layer analysis"]
    Officer(["Compliance Officer"])

    S1 & S2 & S3 & S4 & S5 & S6 & S7 & S8 & S9 & S10 --> Engine
    Engine --> Officer

    subgraph Actions["Recommended Actions"]
        A1["Enhanced Due Diligence"]
        A2["AML Review"]
        A3["KYC Refresh"]
        A4["Risk Reclassification"]
        A5["Escalate to Compliance"]
    end

    Officer --> A1 & A2 & A3 & A4 & A5
```

**Coverage status:**
- ✅ S1 S2 S3 S7 S8 S9 S10 — fully covered by drift engine layers (S10 dormancy break via the explicit `dormancy.py` detector)
- ❌ S4 S5 S6 — entity name change, domain monitoring, and business model pivot not yet implemented

---

## System Use Cases (officer perspective)

```mermaid
flowchart LR
    Officer(["Compliance Officer"])

    subgraph Sentinel["Sentinel · Drift Engine"]
        direction TB
        UC1[Monitor drift dashboard]
        UC2[Scan subject book]
        UC3[Investigate flagged subject]
        UC4[Review causal evidence]
        UC5[Time-travel audit replay]
        UC6[Generate Request for Information]
        UC7["Log decision & rationale\n(from case panel OR drift workspace)"]
        UC8[Export immutable audit log]
        UC9["Switch jurisdiction rules\nCH / EU / HK / AE"]
        UC10[Explore contagion graph]
        UC11[View counterfactual scenarios]
    end

    Officer --> UC1
    Officer --> UC2
    Officer --> UC3
    Officer --> UC7
    Officer --> UC8
    Officer --> UC9
    UC3 --> UC4
    UC3 --> UC5
    UC3 --> UC6
    UC3 --> UC10
    UC3 --> UC11
```

---

## Officer Investigation Flow

```mermaid
sequenceDiagram
    participant O as Compliance Officer
    participant FE as Next.js Frontend
    participant API as FastAPI Backend
    participant DE as Drift Engine
    participant LLM as Claude AI
    participant DB as Database

    O->>FE: Open Drift Dashboard
    FE->>API: GET /api/v1/drift/subjects
    API->>DE: list_subjects()
    DE-->>API: DriftSubjectSummary[] sorted by score
    API-->>FE: Risk-ranked list
    FE-->>O: Radar + priority queue

    O->>FE: Click high-risk subject
    FE->>API: GET /api/v1/drift/subjects/{id}
    API->>DE: get_subject(drift_id)
    DE-->>API: DriftSubjectDetail + all 7 layers
    API-->>FE: Full breakdown + causal evidence
    FE-->>O: Verdict bar · DecisionBar · Evidence panels · Score timeline

    O->>FE: Request AI explanation (SSE)
    FE->>API: GET /api/v1/explanations/{case_id}/stream
    API->>API: anonymizer.pseudonymize()
    API->>LLM: Anonymized case + drift context
    LLM-->>API: Streaming explanation tokens
    API-->>FE: Server-Sent Events
    FE-->>O: Typing animation

    O->>FE: Log decision (drift workspace — no linked case)
    FE->>API: POST /api/v1/decisions\n{drift_id, action, officer_id, rationale?}
    API->>DE: Validate subject + derive recommendation
    API->>DB: INSERT decision + immutable analysis snapshot
    DB-->>API: 201 Created
    API-->>FE: Confirmed
    FE-->>O: Decision recorded — audit event drift_decision_recorded
```

---

## Drift Detection Flow

```mermaid
flowchart TD
    Trigger(["Scheduled Scan\nor Manual Trigger"])

    subgraph Scan["Subject Book Scan"]
        All["Load all subjects\nsimulator.get_book()"]
        Para["Process in parallel\n(stateless per subject)"]
    end

    subgraph Analyze["Per-Subject Analysis — service.py"]
        Layers["Run 7 layers\nbocpd · velocity · contagion\npublic_intel · causal · stability"]
        Fuse["Fuse scores\nConfirmation Lift applied"]
        Route["Cost Cascade\nTier 0 → 1 → 2"]
    end

    subgraph Output["Output"]
        Summary["DriftSubjectSummary\nscore · velocity · action"]
        Detail["DriftSubjectDetail\nper-layer breakdown\ncausal evidence"]
    end

    Action{Recommended Action?}

    Clear["No action\nLow risk"]
    Review["Schedule re-KYC\nMedium risk"]
    Escalate["Enhanced Due Diligence\nHigh risk → Officer queue"]

    Trigger --> All
    All --> Para
    Para --> Layers
    Layers --> Fuse
    Fuse --> Route
    Route --> Summary & Detail
    Summary & Detail --> Action
    Action -->|Clear| Clear
    Action -->|Review| Review
    Action -->|EDD| Escalate

    style Clear fill:#16a34a,color:#fff
    style Review fill:#d97706,color:#fff
    style Escalate fill:#dc2626,color:#fff
```

---

## Time-Travel Audit Flow

```mermaid
flowchart LR
    Officer([Officer])

    SelectDate["Select as-of date\ne.g. 6 months ago"]
    Truncate["Truncate all data\nto that snapshot\n(no future data leaks)"]
    Replay["Re-run full\nDrift Engine analysis"]
    Compare["Compare:\n— Historical score\n— Current score\n— Lead time estimate"]
    Proof["Audit proof:\nSystem would have flagged\nN months before event"]

    Officer --> SelectDate
    SelectDate --> Truncate
    Truncate --> Replay
    Replay --> Compare
    Compare --> Proof
```

---

## Ownership Contagion Discovery

```mermaid
flowchart TD
    Seed["Sanctioned Entity\n(watchlist hit)"]

    Hop1A["Direct shareholder A\n+PageRank weight"]
    Hop1B["Direct shareholder B\n+PageRank weight"]

    Hop2A["2nd-degree owner\nSmaller weight"]
    Hop2B["2nd-degree owner\nSmaller weight"]

    Beyond["3rd degree+\nweight decays to noise"]

    Result["Risk scores updated\nfor connected customers\nnot yet on any watchlist"]

    Seed --> Hop1A & Hop1B
    Hop1A --> Hop2A
    Hop1B --> Hop2B
    Hop2A & Hop2B --> Beyond
    Hop1A & Hop1B & Hop2A & Hop2B --> Result
```
