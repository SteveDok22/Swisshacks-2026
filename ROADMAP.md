# Sentinel · Drift Engine — Task List

Challenge: [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md)

---

## Judging Criteria

| Criterion | Weight | Status |
|---|---|---|
| **AI Intelligence Quality** | 25% | ✅ Strong — 7 real algorithms, causal separation, suspicious stability |
| **Cost Efficiency** | 20% | ⚠️ Partial — T2 LLM works; no per-workflow token count yet |
| **UX & Explainability** | 20% | ⚠️ Gap — 7 visualisations solid; SHAP disconnected from drift; source citations missing |
| **Compliance & Safety** | 20% | ✅ Good — audit log wired; DecisionBar on drift; source citations still missing |
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
| 7 | Dormant company activates | ⚠️ PARTIAL | Stability flags smoothness; no zero→jump detector | `drift/dormancy.py` explicit detector |
| 8 | Legal entity name change | ❌ MISSING | Not implemented | ZEFIX + GLEIF diff; `name_changed` signal |
| 9 | Domain switch / website change | ❌ MISSING | Not implemented | WHOIS + Wayback + Firecrawl |
| 10 | Public business model pivot | ❌ MISSING | Not implemented | EventRegistry + Firecrawl + sentence-transformer cosine |

---

## Tasks

### P0 — Already done ✅

- [x] Wire audit log into drift pipeline — `drift_customer_analyzed`, `drift_scan_completed`, `drift_replay_executed`, etc.
- [x] DecisionBar on drift page — `POST /decisions` accepts `customer_id`; drift recommendations derived server-side
- [x] T2 LLM adjudication — `AnthropicClient` called for T2 customers in `drift/service.py:scan()`
- [x] Audit log frontend page — `GET /api/v1/audit` + `/audit` route in Next.js
- [x] Backend Docker — multi-stage, non-root, healthcheck
- [x] Frontend Docker + compose — `frontend/Dockerfile` + `docker-compose.yml` wired
- [x] BOCPD unit tests — changepoint fires on step series; silent on stationary noise (`test_bocpd.py`)
- [x] Full unit test suite — velocity, causal, stability, cascade, contagion, t2_llm, decisions, score boundaries (15 files)
- [x] BDD scenario tests — drift detection, contagion, audit compliance, API contract (`tests/features/`)

---

### P1 — High impact, do these first

**Engine**
- [ ] **Case 7: Dormancy-break detector** — add `drift/dormancy.py`; detect near-zero baseline → volume jump; wire signal into `drift/service.py`. No external API needed. Moves Case 7 from PARTIAL → WORKS.
- [ ] **Fix BOCPD changepoint visual marker** — `bocpd_changepoint=False` is hardcoded at `service.py:296`; map `bocpd_changepoint_day` to timeline index; add dashed-line marker in `DriftTimeline.tsx`

**Source adapters — `backend/app/sources/` (does not exist yet)**
- [ ] **`sources/base.py`** — `RegistryAdapter` ABC + `EntitySnapshot` + `PublicSignal` diff pattern (shared by all adapters below)
- [ ] **`sources/zefix.py`** — Swiss commercial register; detects name change, legal form change, dissolution, dormancy break (Cases 4, 7, 8, 10)
- [ ] **`sources/gleif.py`** — Global LEI; detects name change, jurisdiction change, parent LEI change (Cases 3, 4, 5, 8, 10)
- [ ] **`sources/opensanctions.py`** — OFAC / EU / UN screening; replaces headline templates in `public_intel.py` (Cases 2, 5)
- [ ] **`sources/open_corporates.py`** — directors / officers / relationships (Cases 3, 4, 5, 7)
- [ ] **`sources/event_registry.py`** — news event aggregation; BOCPD on event-count time-series (Cases 1, 6, 8, 10)
- [ ] **`sources/crunchbase.py`** — funding rounds; scale-jump ratio vs. customer AUM baseline (Case 6)
- [ ] **`sources/firecrawl.py`** — website-to-markdown scraping for current content (Cases 9, 10)
- [ ] **`sources/wayback.py`** — historical website snapshot at onboarding date (Cases 9, 10)
- [ ] **`sources/whois.py`** — RDAP/WHOIS domain age + registrant change (Cases 8, 9)

**Integration glue — without these, adapter work is dead code**
- [ ] **Seed KYC baselines** — populate `db/kyc_baseline.py` with onboarding `EntitySnapshot` from `drift/simulator.py` synthetic customers so adapters have a baseline to diff against
- [ ] **Refactor `public_intel.py` into aggregator** — `service.py:148` calls `generate_signals_for_customer()` which returns headline templates; replace it with real adapter calls (`ZefixAdapter`, `GleifAdapter`, etc.); this is the single wiring step that makes every adapter actually run
- [ ] **Train drift XGBoost model** — `ml/training.py` has no drift scenario training; feed synthetic book (7 scenarios × time windows ≈ 200 samples) through `DriftFeatureExtractor` → label → fit `XGBClassifier`; without this, `DriftFeatureExtractor` produces features nobody scores

**Fusion wiring**
- [ ] **`drift/business_model.py`** — sentence-transformer cosine distance between onboarding snapshot and current website (Cases 9, 10)
- [ ] **`ml/extractors/drift.py`** — `DriftFeatureExtractor` with 20-dim feature vector; wire XGBoost to drift (currently wired to cases only)
- [ ] **`db/kyc_baseline.py`** — store/load `EntitySnapshot` per customer so adapters can diff vs. onboarding state

**UX / explainability**
- [ ] **Source citations on signal cards** — add `source_url` field to `PublicSignalOut` in `public_intel.py`; display in `TwoLayerPanel.tsx`
- [ ] **SHAP wired to drift** — option A (fast): reword README/docs to "per-layer contribution breakdown", remove per-variable SHAP claim; option B (correct): route T1 drift customers through `RiskEngine.score_case`, attach SHAP values to `DriftCustomerDetail`

**Cost tracking**
- [ ] **Token usage per workflow** — add `tokens_used: int` and `model: str` to `CascadeCostReport` in `schemas/drift.py`; populate from `anthropic_client.py` response metadata

---

### P2 — Engineering cleanups

- [ ] Move 6 magic-number layer weights from `service.py:104–163` to named constants in `core/config.py`
- [ ] Add single-worker warning to `service.py:426` global `_engine` singleton (unsafe under multi-process)
- [ ] Remove duplicate timeline endpoint — `GET /drift/customers/{id}/timeline` returns same payload as `GET /drift/customers/{id}`
- [ ] Fix `audit.py:138` — `len(list(...all()))` loads entire table; replace with `COUNT(*)` query
- [ ] `list_customers()` recomputes all 10 customers on every request — add short-lived TTL cache
- [ ] Qualify "real-time signals" language in README and pitch — signals are simulated for MVP; architecture is slot-swap ready

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
| Cost-Aware Cascade | `drift/cascade.py` | T0 rules → T1 XGBoost → T2 LLM |
| Time-Travel Audit | `drift/timetravel.py` | No look-ahead bias on replay |
| Drift Engine | `drift/service.py` | All 7 layers, confirmation lift, LLM adjudication |
| Synthetic Book | `drift/simulator.py` | 7 scenarios with ground-truth labels |
| REST API | `api/v1/` | 28 endpoints, all functional |
| Frontend | `src/app/drift/`, `src/app/audit/` | 7 drift visualisations + audit log page |
| XGBoost + SHAP | `ml/base.py` | Wired to case management only — not drift yet |
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
