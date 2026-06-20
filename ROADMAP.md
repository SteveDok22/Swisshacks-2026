# Sentinel · Drift Engine — Task List

Challenge: [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md)

---

## Judging Criteria

| Criterion | Weight | Status |
|---|---|---|
| **AI Intelligence Quality** | 25% | ✅ Strong — 7 real algorithms, causal separation, suspicious stability |
| **Cost Efficiency** | 20% | ⚠️ Partial — T2 LLM works; no per-workflow token count yet |
| **UX & Explainability** | 20% | ✅ Good — 7 visualisations solid; drift uses per-layer LLR contribution breakdown; signal cards include source citations |
| **Compliance & Safety** | 20% | ✅ Good — audit log wired; DecisionBar on drift; source citations surfaced |
| **Engineering & Architecture** | 15% | ✅ Good — modular engine, clean API, async, unit + BDD tests; no CI/CD |

---

## Use Case Coverage

| # | Use Case | Status | What exists | What's needed |
|---|---|---|---|---|
| 1 | Negative news spike | ⚠️ PARTIAL | Lexicon classifier + confirmation lift; no live feed | EventRegistry adapter + BOCPD on event time-series |
| 2 | Cross-border transfer anomaly | ✅ WORKS | BOCPD + velocity on synthetic data | — |
| 3 | Multiple entities + sudden flows | ⚠️ PARTIAL | Contagion + causal; no named layering detector | GLEIF / OpenCorporates for real UBO graph |
| 4 | Jurisdiction / legal form change | 🔶 INDIRECT | `jurisdiction.py` is rule-pack selector, not change detector | ZEFIX / GLEIF diff vs. KYC baseline |
| 5 | New shareholders / UBOs | ⚠️ PARTIAL | PageRank over synthetic graph; no real UBO lookup | OpenCorporates / GLEIF / OpenSanctions screening |
| 6 | Large funding round / expansion | ⚠️ PARTIAL | `funding_event` template + causal; no live feed | Crunchbase adapter + scale-jump ratio |
| 7 | Dormant company activates | ✅ WORKS | `drift/dormancy.py` explicit detector (near-zero baseline → volume burst); wired into the drift score + surfaced in API; `dormancy_break` scenario in the book | — |
| 8 | Legal entity name change | ❌ MISSING | Not implemented | ZEFIX + GLEIF diff; `name_changed` signal |
| 9 | Domain switch / website change | ❌ MISSING | Not implemented | WHOIS + Wayback + Firecrawl |
| 10 | Public business model pivot | ❌ MISSING | Not implemented | EventRegistry + Firecrawl + sentence-transformer cosine |

---

## Tasks

### P0 — Already done ✅

- [x] Wire audit log into drift pipeline — `drift_subject_analyzed`, `drift_scan_completed`, `drift_replay_executed`, etc.
- [x] DecisionBar on drift page — `POST /decisions` accepts `drift_id`; drift recommendations derived server-side
- [x] T2 LLM adjudication — `AnthropicClient` called for T2 customers in `drift/service.py:scan()`
- [x] Audit log frontend page — `GET /api/v1/audit` + `/audit` route in Next.js
- [x] Backend Docker — multi-stage, non-root, healthcheck
- [x] Frontend Docker + compose — `frontend/Dockerfile` + `docker-compose.yml` wired
- [x] BOCPD unit tests — changepoint fires on step series; silent on stationary noise (`test_bocpd.py`)
- [x] Full unit test suite — velocity, causal, stability, dormancy, cascade, contagion, t2_llm, decisions, score boundaries (16 files)
- [x] BDD scenario tests — drift detection, contagion, audit compliance, API contract (`tests/features/`)

---

### P1 — High impact, do these first

**1. Engine (no external deps)**
- [x] **Case 7: Dormancy-break detector** — `drift/dormancy.py` detects near-zero baseline → volume jump (`dormancy_break = dormancy_depth × activation_strength`); wired into `drift/service.py` (score floor) and surfaced via `DormancyOut` on summary/detail + T2 evidence; `dormancy_break` scenario + "Dormant Holdings AG" seeded in the book; unit + end-to-end tests. **Case 7 PARTIAL → WORKS.** (PR #10)
- [x] **Fix BOCPD changepoint visual marker** — `bocpd_changepoint` is now derived in `DriftEngine.get_subject` by mapping `bocpd_changepoint_day` to its month window (via `SyntheticCustomer.day_to_month`); `DriftTimeline.tsx` renders a violet dashed "Regime change" marker at that month. Unit tests in `test_drift_changepoint_marker.py`. **DONE.** (PR #11)

**2. Prerequisites (build these before adapters)**
- [x] **`db/kyc_baseline.py`** — `EntitySnapshotDB` SQLModel table + `store_snapshot`, `load_latest_snapshot`, `load_onboarding_snapshot`, `load_snapshot_history`, `load_all_baselines` CRUD helpers; registered in `session.py` so the table is auto-created on startup; 24 unit tests covering all helpers and seeding behaviour (PR #11)
- [x] **Seed KYC baselines** — `seed.py:_seed_kyc_baselines()` populates `entity_snapshots` from the synthetic drift book at startup; behavioral baseline (volume, counterparty/corridor risk, margin) computed from the pre-drift window so adapters have a numeric anchor to diff against (PR #11)
- [x] **`sources/base.py`** — `RegistryAdapter` ABC + `EntitySnapshot` + `PublicSignal` diff pattern; shared by all adapters below (PR #13)

**3. Source adapters — `backend/app/sources/` (package does not exist yet)**
- [ ] **`sources/zefix.py`** — Swiss commercial register; name change, legal form, dissolution, dormancy (Cases 4, 7, 8, 10)
- [ ] **`sources/gleif.py`** — Global LEI; name change, jurisdiction change, parent LEI change (Cases 3, 4, 5, 8, 10)
- [ ] **`sources/opensanctions.py`** — OFAC / EU / UN screening (Cases 2, 5)
- [ ] **`sources/open_corporates.py`** — directors / officers / relationships (Cases 3, 4, 5, 7)
- [ ] **`sources/event_registry.py`** — news event aggregation; BOCPD on event-count time-series (Cases 1, 6, 8, 10)
- [ ] **`sources/crunchbase.py`** — funding rounds; scale-jump ratio vs. customer AUM (Case 6)
- [ ] **`sources/firecrawl.py`** — website-to-markdown scraping, current content (Cases 9, 10)
- [ ] **`sources/wayback.py`** — historical website snapshot at onboarding date (Cases 9, 10)
- [ ] **`sources/whois.py`** — RDAP/WHOIS domain age + registrant change (Cases 8, 9)

**4. Integration glue (wire adapters into the engine — without these, adapters are dead code)**
- [ ] **Refactor `public_intel.py` into aggregator** — `service.py:148` calls `generate_signals_for_customer()` which returns fake templates; replace with real adapter calls. This one step makes every adapter actually run.
- [ ] **`drift/business_model.py`** — sentence-transformer cosine distance between onboarding snapshot and current website (Cases 9, 10)
- [ ] **`ml/extractors/drift.py`** — `DriftFeatureExtractor` with 20-dim feature vector; wire XGBoost to drift (currently wired to cases only)
- [ ] **Train drift XGBoost model** — `ml/training.py` has no drift training; feed synthetic book (8 scenarios × time windows ≈ 200 samples) through `DriftFeatureExtractor` → label → `XGBClassifier.fit()`

**5. UX / explainability**
- [ ] **DormancyPanel.tsx** — `DormancyOut` is computed by the engine and included in `DriftSubjectDetail` (API), but the frontend has no panel for it and the TS types are stale: add `DormancyVerdict` interface to `api.ts`; add `dormancy: DormancyVerdict | null` to `DriftSubjectDetail` and `dormancy_break: number` + `is_dormancy_break: boolean` to `DriftSubjectSummary`; create `DormancyPanel.tsx` mirroring `StabilityPanel.tsx` (depth × activation-strength product, flagged banner when `is_dormancy_break`)
- [x] **Source citations on signal cards** — `source_url` field on canonical `PublicSignal` in `sources/base.py` and `PublicSignalOut` in `schemas/drift.py`; synthetic demo signals emit deterministic source references; `PublicSignal` TS type includes `source_url`; `TwoLayerPanel.tsx` renders clickable source links.
- [x] **Drift explainability** — option A chosen: drift attribution is a per-layer LLR contribution breakdown (7 layers × `LayerContribution.llr` + `CausalVerdictOut.contributions` per metric). Per-variable SHAP is case-scoring only; applying it to drift time-series would explain the wrong thing (transaction features ≠ behavioural drift features).

**6. Cost tracking**
- [ ] **Token usage per workflow** — add `tokens_used: int` and `model: str` to `CascadeCostReport` in `schemas/drift.py`; populate from `anthropic_client.py` response metadata

---

### P2 — Engineering cleanups

- [x] Move 6 magic-number layer weights from `service.py` to named constants in `core/config.py`
- [x] Add single-worker warning to the global `_engine` singleton (unsafe under multi-process)
- [x] Remove duplicate timeline endpoint — `GET /drift/subjects/{drift_id}` already returns the timeline
- [x] Fix `db_store.py` — `len(list(...all()))` loads all case IDs for count; replaced with `COUNT(*)` query via `func.count()`
- [x] `list_subjects()` recomputes all 10 subjects on every request — added 30 s TTL cache on `DriftEngine`
- [x] Qualify "real-time signals" language in README and pitch — signals are simulated for MVP; architecture is slot-swap ready

---

### P3 — Nice to have

- [ ] **`time_travel.feature`** BDD test — replay uses only data available at as-of date; lead time is positive
- [ ] **`test_hypothesis_h1.py`** — BOCPD lead time ≥ 2 months on drifting scenarios; 0 false positives on stable scenario
- [ ] **`test_hypothesis_h2.py`** — velocity alert fires earlier than absolute-threshold alert at equal false-positive rate
- [ ] **`test_hypothesis_h3.py`** — 2-hop contagion customers elevated; 3+ hop not elevated
- [ ] **`test_hypothesis_h4.py`** — cascade cost < 10% of LLM-on-everything; high-risk recall unchanged

---

## What Is Already Built (reference)

| Component | File | Notes |
|---|---|---|
| BOCPD | `drift/bocpd.py` | Adams & MacKay 2007, Normal-Inverse-Gamma priors |
| Drift Velocity | `drift/velocity.py` | Closed-form Gaussian KL, smoothed first-differencing |
| Ownership Contagion | `drift/contagion.py` | NetworkX personalized PageRank |
| Causal Drift | `drift/causal.py` | Neyman-Pearson likelihood-ratio |
| Suspicious Stability | `drift/stability.py` | CV × environmental movement |
| Cost-Aware Cascade | `drift/cascade.py` | T0 rules → T1 LLR layer scoring → T2 LLM |
| Time-Travel Audit | `drift/timetravel.py` | No look-ahead bias on replay |
| Drift Engine | `drift/service.py` | All 7 layers, confirmation lift, LLM adjudication |
| Synthetic Book | `drift/simulator.py` | 8 scenarios with ground-truth labels |
| REST API | `api/v1/` | 27 endpoints, all functional |
| Frontend | `src/app/drift/`, `src/app/audit/` | 7 drift visualisations + audit log page |
| XGBoost + SHAP | `ml/base.py` | Wired to case management only; drift uses per-layer LLR breakdown |
| Audit service | `services/audit.py` | Append-only, queried by customer and event type |
| Claude AI | `services/anthropic_client.py` | T2 adjudication + case explanations; mock mode works without key |
| Jurisdiction packs | `services/jurisdiction.py` | CH / EU / HK / AE |

---

## Source → Use Case Matrix

| Source | Cases |
|---|---|
| ZEFIX | 4, 7, 8, 10 |
| GLEIF | 3, 4, 5, 8, 10 |
| OpenCorporates | 3, 4, 5, 7 |
| OpenSanctions | 2, 5 |
| EventRegistry / NewsAPI.ai | 1, 6, 8, 10 |
| Crunchbase | 6 |
| RDAP/WHOIS | 8, 9 |
| Wayback Machine | 9, 10 |
| Firecrawl | 9, 10 |
| Internal transactions | 2, 3, 7 |
