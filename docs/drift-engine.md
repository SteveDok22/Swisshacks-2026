# Drift Engine

## 7-Layer Pipeline

```mermaid
flowchart TD
    Input["Customer Input\nKYC profile · Transactions · AML flags\nPublic signals · Ownership graph"]

    subgraph LayerB["Layer B — Internal Bank Data"]
        L1["1 · Behavioral Drift\nbocpd.py\nBayesian Online Changepoint Detection\n(Adams & MacKay 2007)"]
        L2["2 · Drift Velocity\nvelocity.py\nKL divergence time-derivative\nbits/month"]
        L6["6 · Suspicious Stability\nstability.py\nSlow-walker: anomalously smooth\nwhile environment moves"]
    end

    subgraph LayerA["Layer A — Public Intelligence"]
        L4["4 · Public Intelligence\npublic_intel.py\nNews · Sanctions · Adverse media\nOwnership changes · Funding events"]
    end

    subgraph Topo["Ownership Topology"]
        L3["3 · Ownership Contagion\ncontagion.py\nPersonalized PageRank\n(Page et al. 1999)"]
    end

    Fusion["Confirmation Lift\nTemporal co-occurrence fusion\n(Layer A × Layer B)"]

    L5["5 · Causal Drift\ncausal.py\nLikelihood ratio test\nRisk hypothesis vs benign growth\n(Neyman-Pearson)"]

    L7["7 · Cost-Aware Cascade\ncascade.py\nValue-of-Information routing\n(Howard 1966)"]

    Output["Fused Drift Score  0 – 100\n+ Recommended action\n+ Per-layer contribution\n+ Causal evidence cards\n+ Lead-time estimate"]

    Input --> L1 & L2 & L6
    Input --> L4
    Input --> L3
    L1 & L2 & L6 & L4 --> Fusion
    Fusion --> L5
    L3 --> L5
    L5 --> L7
    L7 --> Output
```

---

## Cost-Aware Cascade (Tier Router)

```mermaid
flowchart TD
    Start([Customer])

    T0{"Tier 0\nRule Engine\nFree — ~95% of customers"}
    T1{"Tier 1\nML · XGBoost + SHAP\n~$0.0002 per customer"}
    T2{"Tier 2\nLLM · Claude Sonnet\n~$0.05 per customer"}

    Clear["Clear\nLow-risk — no action"]
    Review["Review\nScheduled re-KYC"]
    EDD["Escalate\nEnhanced Due Diligence\n+ AI explanation + RFI"]

    Start --> T0
    T0 -->|"Deterministic rules pass\n~95% volume"| Clear
    T0 -->|Borderline| T1
    T1 -->|Score < 40| Clear
    T1 -->|40 ≤ Score < 70| Review
    T1 -->|Score ≥ 70| T2
    T2 -->|Confirms risk| EDD
    T2 -->|Downrates| Review

    style Clear fill:#16a34a,color:#fff
    style Review fill:#d97706,color:#fff
    style EDD fill:#dc2626,color:#fff
```

**Result:** 96% cost reduction vs LLM-on-everything at equal high-risk recall (H4, validated on 1,000-customer synthetic book).

---

## Two-Layer Fusion

```mermaid
flowchart LR
    subgraph A["Layer A — Public Intelligence"]
        News[News & adverse media]
        Sanctions[Sanctions hits]
        Ownership[Ownership changes]
        Funding[Funding events]
    end

    subgraph B["Layer B — Internal Bank Data"]
        BOCPD2[Behavioral drift\nBOCPD score]
        Vel2[Drift velocity\nbits/month]
        TxVol[Transaction volume\npattern shift]
        AML[AML flag history]
    end

    CL["Confirmation Lift\nMultiplied when signals\nco-occur within ±30 days"]

    FusedScore["Fused Drift Score\nWeighted combination\nof all 7 layers"]

    A --> CL
    B --> CL
    CL --> FusedScore
```

---

## Time-Travel Audit

```mermaid
sequenceDiagram
    participant O as Officer
    participant TT as timetravel.py
    participant DE as Drift Engine
    participant DB as Database

    O->>TT: replay(customer_id, as_of_date)
    TT->>DB: Fetch data WHERE timestamp ≤ as_of_date
    TT->>DB: Fetch public signals WHERE date ≤ as_of_date
    TT->>DB: Fetch contagion edges WHERE listed_at ≤ as_of_date

    note over TT: Strictly truncates future data —\nno look-ahead bias

    TT->>DE: run_full_analysis(truncated_snapshot)
    DE-->>TT: Historical drift score + evidence
    TT-->>O: ReplayResult\n(score, lead_time, what_was_known)

    note over O: Proves the system would\nhave flagged this customer\nwithout hindsight
```

---

## Validation Results

| Hypothesis | Scenario | Result |
|---|---|---|
| H1 — Lead time | Changepoint on step data, none on stationary | 2–7 months lead (median 5.5), 0 false positives |
| H2 — Velocity leads level | Velocity vs absolute-threshold alerting | Velocity fires earlier at equal FP rate |
| H3 — Contagion propagates | Personalized PageRank from sanctioned seed | 2-hop customers elevated; distant unaffected |
| H4 — Cascade cost reduction | Cascade vs LLM-on-everything, 1,000 customers | 96% cost reduction at equal recall |
| Causal classification | 11 scenarios with ground truth | 11/11 correct, 8/8 seed robustness |
| Stability classification | 13 scenarios with ground truth | 13/13 correct, 8/8 seed robustness |
