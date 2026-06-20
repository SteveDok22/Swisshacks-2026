# Sentinel — Source Integration Architecture

> Next-step design: how external registry, news, and web-monitoring connectors
> plug into the signal layer, how signals are rated, and how ML fusion produces
> the final drift score.
>
> Companion to [`architecture.md`](architecture.md) and [`drift-engine.md`](drift-engine.md).
> For the **free-vs-paid decision per source** and the current scaffolding
> status, see [`sources.md`](sources.md).

> **Status — scaffolding (carcass).** `backend/app/sources/` now exists with the
> shared contract (`RegistryAdapter`, `EntitySnapshot`, generic field-diff) and a
> carcass per source. No adapter does real network I/O yet. Of the connectors
> below, **7 are free and will be implemented** (ZEFIX, GLEIF, OpenSanctions,
> GDELT, Firecrawl, Wayback, WHOIS/RDAP) and **3 are paid and skipped**
> (OpenCorporates, Event Registry, Crunchbase). GDELT is the free, key-less news
> feed that replaces the paid Event Registry. Details + rationale in
> [`sources.md`](sources.md).

---

## 1. Current State vs. Target

```
TODAY                                  TARGET
─────────────────────────────────────  ─────────────────────────────────────
Synthetic customer book only           Real KYC baseline stored per customer
Template headlines (no real APIs)      Real source adapters (9 connectors)
Lexicon severity classifier            Severity = adapter-specific formula
XGBoost wired to CASE only             XGBoost wired to DRIFT feature vector
SHAP disconnected from drift           SHAP per-signal contribution in UI
"public_risk" = single float           Signal list with citations + months
```

---

## 2. Top-Level System Architecture

```mermaid
graph TB
    subgraph TRIGGERS["Trigger Layer"]
        SCHED[Scheduled Poller<br/>nightly per customer]
        EVT[Event Hook<br/>webhook / on-demand]
    end

    subgraph SOURCES["Source Adapters  ·  sources/"]
        Z[ZefixAdapter<br/>CH registry]
        G[GleifAdapter<br/>global LEI]
        OC[OpenCorporatesAdapter<br/>directors / officers]
        OS[OpenSanctionsAdapter<br/>OFAC · EU · UN]
        ER[EventRegistryAdapter<br/>news aggregation]
        CB[CrunchbaseAdapter<br/>funding rounds]
        FC[FirecrawlAdapter<br/>website content]
        WB[WaybackAdapter<br/>historical snapshots]
        WH[WhoisAdapter<br/>domain registration]
    end

    subgraph SIGNALS["Signal Layer  ·  drift/public_intel.py"]
        SIG[PublicSignal<br/>type · severity · source_url · month]
        DIFF[Diff Engine<br/>current vs KYC baseline]
        BOCPD_S[BOCPD on signal<br/>time-series<br/>spike detection]
    end

    subgraph INTERNAL["Internal Layer  ·  drift/service.py"]
        BOCPD_I[BOCPD on tx volume]
        VEL[Drift Velocity<br/>KL divergence]
        CONT[Ownership Contagion<br/>PageRank]
        CAU[Causal Assessment<br/>LLR test]
        STAB[Suspicious Stability<br/>CV × env movement]
    end

    subgraph FUSION["Fusion Layer  ·  ml/base.py  +  drift/service.py"]
        LIFT[Confirmation Lift<br/>temporal co-occurrence]
        XGB[XGBoost<br/>feature vector → score]
        SHAP[SHAP<br/>per-signal contribution]
    end

    subgraph CASCADE["Cost-Aware Cascade  ·  drift/cascade.py"]
        T0[T0 — Rules<br/>100% of book · free]
        T1[T1 — XGBoost<br/>anomalous only · $0.0002]
        T2[T2 — LLM Claude<br/>borderline · $0.05]
    end

    subgraph OUTPUT["Officer Output"]
        DASH[Drift Dashboard<br/>score · layers · signals]
        DEC[DecisionBar<br/>Allow · Step-up · Escalate · Block]
        AUD[Audit Log<br/>append-only]
    end

    TRIGGERS --> SOURCES
    SOURCES --> DIFF
    DIFF --> SIG
    SIG --> BOCPD_S
    BOCPD_S --> LIFT
    INTERNAL --> LIFT
    LIFT --> XGB
    XGB --> SHAP
    XGB --> CASCADE
    CASCADE --> T0
    T0 --> T1
    T1 --> T2
    T2 --> DASH
    DASH --> DEC
    DEC --> AUD
```

---

## 3. Source Adapter Pattern — One Base Class, Nine Implementations

Every external source follows the **fetch → normalize → diff → signal** pipeline.

```mermaid
classDiagram
    class RegistryAdapter {
        <<abstract>>
        +source_id: str
        +base_url: str
        +fetch(entity_id) dict
        +normalize(raw) EntitySnapshot
        +diff(baseline, current) list~PublicSignal~
        +fetch_and_diff(entity_id, baseline) list~PublicSignal~
    }

    class EntitySnapshot {
        +entity_id: str
        +legal_name: str
        +legal_form: str
        +jurisdiction: str
        +registered_address: str
        +owners: list~str~
        +status: str
        +fetched_at: datetime
        +raw: dict
    }

    class PublicSignal {
        +signal_type: str
        +headline: str
        +severity: float
        +source: str
        +source_url: str
        +month: int
        +raw_evidence: dict
    }

    class ZefixAdapter
    class GleifAdapter
    class OpenCorporatesAdapter
    class OpenSanctionsAdapter
    class EventRegistryAdapter
    class CrunchbaseAdapter
    class FirecrawlAdapter
    class WaybackAdapter
    class WhoisAdapter

    RegistryAdapter <|-- ZefixAdapter
    RegistryAdapter <|-- GleifAdapter
    RegistryAdapter <|-- OpenCorporatesAdapter
    RegistryAdapter <|-- OpenSanctionsAdapter
    RegistryAdapter <|-- EventRegistryAdapter
    RegistryAdapter <|-- CrunchbaseAdapter
    RegistryAdapter <|-- FirecrawlAdapter
    RegistryAdapter <|-- WaybackAdapter
    RegistryAdapter <|-- WhoisAdapter

    RegistryAdapter --> EntitySnapshot
    RegistryAdapter --> PublicSignal
```

**Fetch → diff sequence (same for every adapter):**

```mermaid
sequenceDiagram
    participant Sched as Scheduler
    participant Adapter as RegistryAdapter
    participant API as External API
    participant KYC as KYC Baseline Store
    participant Diff as Diff Engine
    participant Sig as Signal List

    Sched->>Adapter: fetch_and_diff(entity_id, baseline)
    Adapter->>KYC: load_baseline(entity_id)
    KYC-->>Adapter: EntitySnapshot (onboarding)
    Adapter->>API: GET /api/entity/{id}
    API-->>Adapter: raw JSON
    Adapter->>Adapter: normalize(raw) → EntitySnapshot (current)
    Adapter->>Diff: diff(baseline, current)
    Diff->>Diff: compare fields field-by-field
    Diff-->>Sig: [PublicSignal, ...] only changed fields
```

---

## 4. Per-Connector Detail

### 4a. ZEFIX — Swiss Commercial Register (Cases 4, 7, 8, 10)

API base: `https://www.zefix.admin.ch/ZefixPublicREST/api/v1` (free, no key)

```mermaid
flowchart LR
    A["GET /company/{uid}"] --> B["normalize()"]
    B --> C{diff vs baseline}
    C -->|legal_name changed| D["PublicSignal<br/>type=name_change<br/>severity=0.85"]
    C -->|legal_form changed<br/>e.g. GmbH→SA| E["PublicSignal<br/>type=jurisdiction_change<br/>severity=0.70"]
    C -->|status=dissolved| F["PublicSignal<br/>type=adverse_media<br/>severity=0.90"]
    C -->|registered_address → offshore| G["PublicSignal<br/>type=jurisdiction_change<br/>severity=0.65"]
    C -->|mutation_date after dormancy| H["PublicSignal<br/>type=dormancy_break<br/>severity=0.75"]
```

Fields tracked: `name`, `legalSeat`, `legalForm`, `status`, `uid`, `mutationDate`.

Severity formula for name change:
```
severity = 0.75 + 0.10 × (levenshtein_distance / max(len_a, len_b))
           capped at 0.90
```
Small typo corrections → ~0.76. Complete rebrand → 0.90.

---

### 4b. GLEIF — Global Legal Entity Identifier (Cases 3, 4, 5, 8, 10)

API base: `https://api.gleif.org/api/v1`

```mermaid
flowchart LR
    A["GET /lei-records/{lei}"] --> B["normalize()"]
    A2["GET /lei-records/{lei}/ultimate-parent"] --> B
    A3["GET /lei-records/{lei}/direct-children"] --> B
    B --> C{diff vs baseline}
    C -->|entity.legalName changed| D["PublicSignal<br/>name_change · 0.85"]
    C -->|entity.status = ANNULLED| E["PublicSignal<br/>adverse_media · 0.95"]
    C -->|jurisdiction changed| F["PublicSignal<br/>jurisdiction_change · 0.70"]
    C -->|ultimate parent LEI changed| G["PublicSignal<br/>ownership_change · 0.75"]
    C -->|new child LEI added| H["PublicSignal<br/>ownership_change · 0.50"]
```

Key endpoints:
- `/lei-records/{lei}` — entity status, legal name, jurisdiction
- `/lei-records/{lei}/ultimate-parent` — top-of-chain UBO entity
- `/lei-records/{lei}/direct-children` — subsidiaries
- `/lei-records?filter[entity.legalName]=...` — reverse name lookup

---

### 4c. OpenSanctions — Watchlist Screening (Cases 2, 5)

API base: `https://api.opensanctions.org` — free tier, 30 req/min.

```mermaid
flowchart LR
    A["GET /search/default?q={name}&schema=Company"] --> B["normalize()"]
    B --> C{match score?}
    C -->|> 0.85| D["PublicSignal<br/>type=sanctions<br/>severity=0.95"]
    C -->|0.65–0.85| E["PublicSignal<br/>type=sanctions<br/>severity=0.70"]
    C -->|< 0.65| F[no signal emitted]
    D --> G[screen each UBO<br/>from GLEIF owner list]
    G --> H{owner hit?}
    H -->|yes| I["PublicSignal<br/>ownership_change · 0.90<br/>headline: 'UBO on OFAC list'"]
```

Match score comes from OpenSanctions' built-in name-matching engine.
Threshold 0.85 → ~99% precision on entity names.

---

### 4d. EventRegistry — News Event Aggregation (Cases 1, 6, 8, 10)

EventRegistry groups 20–50 articles into a single `Event` object, so spike
detection operates on event-level aggregation rather than raw article count —
much more robust against SEO noise and syndication spam.

```mermaid
flowchart TB
    A["POST /api/v1/getEvents<br/>{keyword: entity_name,<br/> dateStart: last_30d,<br/> categoryWeights: negative}"] --> B["list of Event objects"]
    B --> C["group by month → event_count[month]"]
    C --> D["BOCPD on event_count time-series"]
    D --> E{regime change?}
    E -->|yes| F["spike_score = delta_lambda / baseline_sigma"]
    F --> G["PublicSignal<br/>type=news<br/>severity = classify_headline × spike_amplifier<br/>source_url = event.url"]
    E -->|no| H["PublicSignal low-severity<br/>if any events exist<br/>severity = max(classify_headline)"]
```

Severity classification — two-stage pipeline:

```mermaid
flowchart LR
    T["event.title + event.summary"] --> LEX{lexicon match?}
    LEX -->|keyword hit| S1[lexicon score]
    LEX -->|no match| EMB["sentence-transformer<br/>cosine sim to risk templates"]
    S1 --> W[weighted average]
    EMB --> W
    W --> SPIKE{spike active?}
    SPIKE -->|yes| AMP["× 1.3 capped at 0.95"]
    SPIKE -->|no| FINAL[severity output]
    AMP --> FINAL
```

---

### 4e. Crunchbase — Funding & Scale Events (Case 6)

```mermaid
flowchart LR
    A["GET /entities/organizations/{permalink}/funding_rounds"] --> B["latest_round"]
    B --> C["scale_jump_ratio = round_amount / customer_aum_baseline"]
    C --> D{ratio}
    D -->|> 10×| E["funding_event · 0.75"]
    D -->|5–10×| F["funding_event · 0.55"]
    D -->|2–5×| G["funding_event · 0.35"]
    D -->|< 2×| H[no signal]
    E --> I[screen new investors via OpenSanctions]
    I --> J{investor hit?}
    J -->|yes| K["ownership_change · 0.85"]
```

---

### 4f. Firecrawl + Wayback Machine — Website Content Drift (Cases 9, 10)

The most complex connector: uses embedding comparison rather than field diffing.

```mermaid
flowchart TB
    A["Wayback Machine<br/>GET /wayback/available?url={domain}<br/>&timestamp={onboarding_date}"] --> B[fetch onboarding snapshot URL]
    B --> C["Firecrawl<br/>POST /scrape {url: snapshot_url}"]
    C --> D[onboarding_text markdown]

    E["Firecrawl<br/>POST /scrape {url: current_domain}"] --> F[current_text markdown]

    D --> G["sentence-transformers<br/>embed(onboarding_text)"]
    F --> H["sentence-transformers<br/>embed(current_text)"]

    G --> I["cosine_distance(embed_A, embed_B)"]
    H --> I

    I --> J{distance}
    J -->|> 0.50| K["business_model_change · 0.85"]
    J -->|0.30–0.50| L["business_model_change · 0.55"]
    J -->|< 0.30| M[no signal]
```

---

### 4g. WHOIS / RDAP — Domain Registration (Case 9)

```mermaid
flowchart LR
    A["RDAP GET /domain/{domain}"] --> B[registration_date + registrant]
    B --> C{domain_age_days}
    C -->|< 30| D["domain_change · 0.80"]
    C -->|30–180| E["domain_change · 0.45"]
    C -->|> 180| F[no age signal]
    B --> G{registrant changed vs baseline?}
    G -->|yes| H["domain_change · 0.70"]
```

---

## 5. Signal Schema and Severity Scale

Every adapter emits the same `PublicSignal`. After the migration, `public_intel.py`
becomes an **aggregator** that calls adapters rather than generating templates.

| Severity | Meaning | Examples |
|---|---|---|
| 0.90–1.00 | Near-certain escalation trigger | OpenSanctions hit, entity ANNULLED |
| 0.75–0.89 | Strong — high priority | Legal name change, domain age < 30d |
| 0.60–0.74 | Moderate — investigate | Jurisdiction move, parent LEI changed |
| 0.40–0.59 | Informational — monitor | New subsidiary, small funding round |
| 0.10–0.39 | Background noise | Awards, partnerships, minor press |
| 0.00 | Suppressed | Confirmed typo correction |

**Severity formulas per signal type:**

```mermaid
flowchart TD
    T{signal_type}
    T -->|sanctions| S1["0.70 + 0.25 × match_score"]
    T -->|name_change| S2["0.75 + 0.10 × levenshtein_norm"]
    T -->|jurisdiction_change| S3["0.40 + 0.30 × jurisdiction_risk_delta"]
    T -->|ownership_change| S4["0.40 + 0.40 × owner_sanctions_score"]
    T -->|funding_event| S5["clip(0.20 + 0.08 × log10(scale_ratio), 0, 0.80)"]
    T -->|news| S6["lexicon_score × (1 + 0.3 × spike_active)"]
    T -->|business_model_change| S7["clip(0.20 + 1.30 × cosine_distance, 0, 0.95)"]
    T -->|domain_change| S8["0.80 if age<30d else 0.45 if age<180d"]
    T -->|dormancy_break| S9["0.60 + 0.15 × volume_jump_factor"]
```

---

## 6. BOCPD Applied to Public Signal Time-Series

BOCPD already runs on internal transaction volume. The same algorithm wraps
the news event-count time-series for spike detection (Use Case 1).

```mermaid
sequenceDiagram
    participant ER as EventRegistry
    participant AGG as Signal Aggregator
    participant BOCPD as BOCPD Engine
    participant LIFT as Confirmation Lift

    ER->>AGG: events per month for customer (12 months)
    AGG->>AGG: event_count[month] time-series
    AGG->>BOCPD: run(standardize(event_count))
    BOCPD-->>AGG: BocpdResult(detected_changepoints, run_lengths)
    AGG->>AGG: if changepoint: spike_score = delta_lambda / sigma_baseline
    AGG->>LIFT: (public_peak_month, spike_score)
    Note over LIFT: same temporal alignment check used for<br/>internal drift confirmation lift
```

This means the existing confirmation-lift gate handles news spikes automatically:
if the internal BOCPD fires on volume **and** the news BOCPD fires on event count
within the same 30-day window, lift amplifies both signals.

---

## 7. Full Fusion Pipeline — How a Score Is Built

```mermaid
flowchart TB
    subgraph PUBLIC["Public Layer (new)"]
        P1[signals from all adapters]
        P2[BOCPD on news time-series]
        P3["public_risk = weighted_max(all severities)"]
        P4[public_peak_month]
        P1 --> P2
        P1 --> P3
        P2 --> P4
    end

    subgraph INTERNAL["Internal Layer (existing)"]
        I1[BOCPD on tx volume]
        I2[drift velocity KL divergence]
        I3[ownership contagion PageRank]
        I4[causal LLR p_risk]
        I5[suspicious stability CV × env]
        I1 --> I6[internal_risk 0-1]
        I2 --> I6
        I3 --> I6
        I4 --> I7[causal_factor 0.45-1.0]
        I5 --> I8[stability_elevation]
        I6 --> I9[internal_peak_month]
    end

    subgraph LIFT["Confirmation Lift"]
        CL["lift = f(public_risk, internal_risk,<br/>public_peak_month, internal_peak_month)<br/>gates on min-floor · temporal window ±1 month"]
    end

    subgraph SCORE["Score Assembly"]
        SC1["base = max(internal_risk, public_risk × 0.85)"]
        SC2["amplification = 1.0 + clip((lift-1)/3, 0, 1) × 0.35"]
        SC3["score = base × amplification × 100"]
        SC4["score = score × causal_factor"]
        SC5["if stability.is_suspicious: score = max(score, 50 + suspicion×40)"]
        SC1 --> SC2 --> SC3 --> SC4 --> SC5
    end

    subgraph XGBOOST["XGBoost Fusion (replaces manual weights)"]
        XF[feature vector — 20 dims]
        XGB[XGBoost model]
        XS[SHAP values per feature]
        XF --> XGB --> XS
    end

    PUBLIC --> CL
    INTERNAL --> CL
    CL --> SCORE
    SCORE --> XGBOOST
    XGBOOST --> CASCADE[Cost-Aware Cascade]
```

---

## 8. XGBoost Feature Vector — What Goes In

The existing XGBoost model scores **cases** via a case feature extractor.
A parallel `DriftFeatureExtractor` feeds the same `RiskModel` class for drift.

```mermaid
graph LR
    subgraph INTERNAL_FEATS["Internal Features"]
        F1[drift_score 0-100]
        F2[max_velocity bits/month]
        F3[final_drift bits]
        F4[causal_p_risk 0-1]
        F5[stability_suspicion 0-1]
        F6[propagated_risk 0-1]
        F7[bocpd_changepoint_day int or -1]
    end

    subgraph PUBLIC_FEATS["Public Signal Features  (new)"]
        F8[n_signals count]
        F9[max_severity 0-1]
        F10[news_spike_score 0-1]
        F11[sanctions_hit binary]
        F12[name_changed binary]
        F13[ownership_changed binary]
        F14[funding_scale_ratio float]
        F15[business_model_drift 0-1]
        F16[domain_changed binary]
        F17[dormancy_break binary]
        F18[jurisdiction_risk_delta -1 to +1]
    end

    subgraph TEMPORAL_FEATS["Temporal Features  (new)"]
        F19[confirmation_lift 1.0-4.0]
        F20[days_since_last_public_signal int]
    end

    F1 & F2 & F3 & F4 & F5 & F6 & F7 --> XGB[XGBoost<br/>DriftFeatureExtractor]
    F8 & F9 & F10 & F11 & F12 & F13 & F14 & F15 & F16 & F17 & F18 --> XGB
    F19 & F20 --> XGB
    XGB --> SCORE[risk_score 0-100]
    XGB --> SHAP["SHAP values → UI layer cards<br/>with source_url citations"]
```

**Why XGBoost replaces manual weights:** `service.py` currently uses 6 hardcoded
magic-number weights (`0.6 × vel_norm + 0.25 × drift_norm + 0.4 × prop_risk`).
With 20 real features these weights become unmanageable and opaque. XGBoost
learns interaction weights from the labeled synthetic book (ground-truth scenarios),
and SHAP makes each weight explainable — the officer sees "score driven 40% by
`news_spike`, 30% by `ownership_changed`, 20% by `drift_velocity`."

**Training setup:**
- Data: 7 synthetic scenarios × multiple time windows ≈ 200 labeled samples
- Labels: `{risk, benign, ambiguous}` from simulator ground truth
- Model: `XGBClassifier` + Platt scaling → probability → 0–100 score
- SHAP: `TreeExplainer(model).shap_values(feature_vector)` → per-feature contribution list

---

## 9. SHAP → UI Layer Cards

```mermaid
sequenceDiagram
    participant XGB as XGBoost Model
    participant SHAP as SHAP TreeExplainer
    participant API as GET /drift/customers/{id}
    participant UI as TwoLayerPanel.tsx

    XGB->>SHAP: shap_values(drift_feature_vector)
    SHAP-->>API: [(feature_name, shap_value), ...]
    Note over API: Map feature names to human labels:<br/>"news_spike_score" → "EventRegistry news spike"<br/>"sanctions_hit" → "OpenSanctions OFAC hit"<br/>"name_changed" → "ZEFIX: legal name changed"
    API-->>UI: LayerContribution list with shap_value as llr
    UI->>UI: render per-layer bar with source_url citation link
```

---

## 10. Cost-Aware Cascade — Full Decision Tree

```mermaid
flowchart TD
    START[Customer signal] --> T0{T0 — Deterministic Rules}
    T0 -->|sanctions_hit OR name_changed OR status=ANNULLED| ESC0["→ ESCALATE immediately<br/>skip T1 and T2  ·  cost = $0"]
    T0 -->|drift_score < 30| ALLOW["→ ALLOW  ·  cost = $0"]
    T0 -->|30 ≤ score < 55| T1{T1 — XGBoost}
    T0 -->|score ≥ 55| T2
    T1 -->|score < 40 after XGB| STEPUP["→ STEP-UP VERIFICATION  ·  cost = $0.0002"]
    T1 -->|score ≥ 40| T2{T2 — LLM Claude}
    T2 -->|verdict=benign confidence > 0.7| ALLOW2["→ ALLOW  ·  cost = $0.0252"]
    T2 -->|verdict=risk confidence > 0.7| BLOCK["→ BLOCK / ESCALATE  ·  cost = $0.0252"]
    T2 -->|ambiguous or confidence < 0.7| HITL["→ HUMAN REVIEW<br/>DecisionBar activated  ·  cost = $0.0252"]

    style ESC0 fill:#dc2626,color:#fff
    style ALLOW fill:#16a34a,color:#fff
    style ALLOW2 fill:#16a34a,color:#fff
    style BLOCK fill:#dc2626,color:#fff
    style HITL fill:#d97706,color:#fff
    style STEPUP fill:#ca8a04,color:#fff
```

---

## 11. End-to-End Flow — Use Case 8: Legal Entity Name Change

*Swiss company secretly renamed — one of the three previously-missing use cases.*

```mermaid
sequenceDiagram
    participant SCHED as Nightly Scheduler
    participant ZEFIX as ZefixAdapter
    participant GLEIF as GleifAdapter
    participant OS as OpenSanctionsAdapter
    participant DIFF as Diff Engine
    participant SIG as Signal Aggregator
    participant ENG as DriftEngine
    participant CAS as CascadeRouter
    participant LLM as Claude T2
    participant AUD as AuditService
    participant UI as Officer UI

    SCHED->>ZEFIX: fetch_and_diff("CHE-123.456.789", baseline)
    ZEFIX->>ZEFIX: GET /ZefixREST/api/v1/company/CHE-123.456.789
    ZEFIX->>DIFF: diff(baseline_snapshot, current_snapshot)
    DIFF-->>SIG: PublicSignal(name_change, severity=0.85, source_url="zefix.admin.ch/...")

    SCHED->>GLEIF: fetch_and_diff("529900HNOAA1KXQJUQ27", baseline)
    GLEIF-->>SIG: PublicSignal(name_change, severity=0.85, source_url="gleif.org/...")

    SIG->>OS: screen_name("New Corporate Name AG")
    OS-->>SIG: no match

    SIG->>ENG: signals=[name_change×2], internal_drift_score=38
    ENG->>ENG: public_risk = 0.85
    ENG->>ENG: confirmation_lift = 1.8  (two sources confirm same event)
    ENG->>ENG: base = max(internal_risk, 0.85×0.85) = 0.72
    ENG->>ENG: score = 0.72 × 1.13 × 100 = 81.4

    ENG->>CAS: route(score=81.4, name_changed=True)
    CAS->>CAS: T0: name_changed=True → skip to ESCALATE
    CAS-->>UI: reached_tier=T2_LLM, recommended_action=ESCALATE

    ENG->>LLM: adjudicate(context=name_change evidence and internal signals)
    LLM-->>ENG: verdict=risk, confidence=0.91, recommended_action=Trigger KYC refresh
    Note over LLM,ENG: rationale: Legal entity rename without disclosed business reason<br/>internal drift elevated — re-KYC required

    ENG->>AUD: log(drift_customer_analyzed, customer_id, score=81.4, name_changed=True)
    UI->>UI: render DecisionBar with AI recommendation=ESCALATE
    UI->>AUD: officer submits ESCALATE + rationale
    AUD->>AUD: append-only: drift_decision_recorded
```

---

## 12. Sprint Sequence — Ordered by Impact

```mermaid
gantt
    title Implementation Sprints
    dateFormat  YYYY-MM-DD
    section Sprint 0 — no APIs needed
    Case 7 dormancy-break detector          :s0a, 2026-06-20, 2h
    Fix BOCPD visual marker in timeline     :s0b, after s0a, 1h
    Source citations on signal cards        :s0c, after s0b, 1h

    section Sprint 1 — registry APIs
    RegistryAdapter base class              :s1a, after s0c, 1h
    ZefixAdapter + Case 8 name change       :s1b, after s1a, 2h
    GleifAdapter + Case 4 jurisdiction      :s1c, after s1b, 2h
    OpenSanctionsAdapter + Case 5 UBO       :s1d, after s1c, 2h
    DriftFeatureExtractor + XGBoost wiring  :s1e, after s1d, 3h

    section Sprint 2 — news + funding
    EventRegistryAdapter + BOCPD on signals :s2a, after s1e, 3h
    Case 1 news spike WORKS                 :s2b, after s2a, 1h
    CrunchbaseAdapter + Case 6              :s2c, after s2b, 2h
    SHAP wired to drift layer cards         :s2d, after s2c, 2h

    section Sprint 3 — web monitoring
    FirecrawlAdapter + WaybackAdapter       :s3a, after s2d, 3h
    WhoisAdapter + Case 9 domain switch     :s3b, after s3a, 2h
    Case 10 business model pivot            :s3c, after s3b, 2h
```

---

## 13. File Layout — What Gets Created

```
backend/app/
├── sources/                        ← NEW package (carcass — scaffolding only)
│   ├── __init__.py                 ← exports contract + adapters + registry
│   ├── base.py                     ← RegistryAdapter ABC + EntitySnapshot +
│   │                                  PublicSignal + SnapshotDiff/diff_snapshots
│   ├── cost.py                     ← SourceCost/AdapterStatus + CostMixin +
│   │                                  SourceUnavailableError (free-vs-paid layer)
│   ├── registry.py                 ← REGISTRY catalogue + usable/skipped helpers
│   ├── zefix.py                    ← ZefixAdapter            (FREE  · implement)
│   ├── gleif.py                    ← GleifAdapter            (FREE  · implement)
│   ├── opensanctions.py            ← OpenSanctionsAdapter    (FREEMIUM · implement)
│   ├── gdelt.py                    ← GdeltAdapter  NEW       (FREE  · implement)
│   ├── firecrawl.py                ← FirecrawlAdapter        (FREEMIUM · implement)
│   ├── wayback.py                  ← WaybackAdapter          (FREE  · implement)
│   ├── whois.py                    ← WhoisAdapter            (FREE  · implement)
│   ├── open_corporates.py          ← OpenCorporatesAdapter   (PAID  · SKIPPED)
│   ├── event_registry.py           ← EventRegistryAdapter    (PAID  · SKIPPED)
│   └── crunchbase.py               ← CrunchbaseAdapter       (PAID  · SKIPPED)
│
├── drift/
│   ├── public_intel.py             ← becomes aggregation layer not generation
│   ├── dormancy.py                 ← NEW: explicit dormancy-break detector
│   └── business_model.py           ← NEW: sentence-transformer cosine comparator
│
├── ml/
│   └── extractors/
│       ├── social_engineering.py   (existing)
│       └── drift.py                ← NEW: DriftFeatureExtractor (20 features)
│
└── db/
    └── kyc_baseline.py             ← NEW: store/load EntitySnapshot per customer
```

---

## 14. Source → Use Case Coverage Matrix

| Source | Use Cases | Cost | Decision |
|---|---|---|---|
| ZEFIX | 4, 7, 8, 10 | FREE | ✅ implement |
| GLEIF | 3, 4, 5, 8, 10 | FREE | ✅ implement |
| OpenSanctions | 2, 5 | FREEMIUM | ✅ implement |
| GDELT | 1, 6, 8, 10 | FREE | ✅ implement (replaces Event Registry) |
| Firecrawl | 9, 10 | FREEMIUM | ✅ implement |
| Wayback Machine | 9, 10 | FREE | ✅ implement |
| RDAP / WHOIS | 8, 9 | FREE | ✅ implement |
| OpenCorporates | 3, 4, 5, 7 | PAID | ⛔ skip (covered by GLEIF + ZEFIX) |
| EventRegistry / NewsAPI.ai | 1, 6, 8, 10 | PAID | ⛔ skip (covered by GDELT) |
| Crunchbase | 6 | PAID | ⛔ skip (partial via GDELT news) |
| Internal transactions | 2, 3, 7 | — | already built |

After the free sprints: **10/10 use cases covered with 7 free adapters** (no paid
dependency), up from 1 fully working today.
