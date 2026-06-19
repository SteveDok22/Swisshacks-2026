# Sentinel · Drift Engine — Roadmap

Current status: **core statistical engine complete; compliance loop, LLM integration, and 3 of 10 challenge use cases have gaps.**

Challenge: [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md)

---

## Judging Criteria — Honest Self-Assessment

| Criterion | Weight | Status | Notes |
|---|---|---|---|
| **AI Intelligence Quality** | 25% | ✅ Strong | 7 real algorithms, genuine causal separation, suspicious stability |
| **Cost Efficiency** | 20% | ⚠️ Gap | Cascade well-designed; T2 LLM calls counted but never executed; no per-workflow token count |
| **UX & Explainability** | 20% | ⚠️ Gap | 7 visualisations solid; SHAP disconnected from drift; source citations missing |
| **Compliance & Safety** | 20% | ⚠️ Gap | Anonymizer works; ~~audit log not written from drift~~ fixed; HITL missing on drift page |
| **Engineering & Architecture** | 15% | ✅ Good | Modular 10-file engine, clean API, async throughout; no tests, no CI/CD |

---

## What Is Complete

### Statistical Core

| Component | File | Algorithm |
|---|---|---|
| Bayesian Online Changepoint Detection | `drift/bocpd.py` | Adams & MacKay 2007, Normal-Inverse-Gamma priors |
| KL Divergence + Drift Velocity | `drift/velocity.py` | Closed-form Gaussian KL, smoothed first-differencing |
| Ownership Contagion | `drift/contagion.py` | NetworkX personalized PageRank with seed nodes |
| Causal Drift (LLR test) | `drift/causal.py` | Neyman-Pearson likelihood-ratio, risk vs benign |
| Suspicious Stability | `drift/stability.py` | Multiplicative CV × environmental movement |
| Cost-Aware Cascade | `drift/cascade.py` | Cumulative-cost accounting (T2 pays T0+T1+T2) |
| Time-Travel Audit | `drift/timetravel.py` | Truncation applied to behavioral, public, contagion sources |
| Drift Engine Orchestrator | `drift/service.py` | All 7 layers wired, two-layer fusion, confirmation lift |
| Synthetic Book | `drift/simulator.py` | 7 scenarios with explicit ground truth |

### Platform

| Area | Status |
|---|---|
| REST API | 27 endpoints, all functional |
| Frontend — 7 drift visualizations | All render real API data |
| XGBoost + SHAP | Real — wired to case management only, not drift |
| Audit service | Append-only, SQLite-persisted |
| Privacy / anonymizer | PII pseudonymized before Claude |
| Claude AI integration | Works for case explanations; not connected to drift |
| Jurisdiction rule packs | CH / EU / HK / AE all loaded |
| Docker | Backend Dockerfile production-quality (multi-stage, non-root, healthcheck) |

### Challenge Use Case Coverage

| Use Case | Signal | Status |
|---|---|---|
| Negative news spike | Reputational risk | ✅ public_intel.py severity + Confirmation Lift |
| Cross-border transfer anomaly | Behavioural anomaly | ✅ BOCPD + velocity |
| Multiple entities + sudden flows | Structuring / layering | ✅ contagion + causal |
| Jurisdiction / legal form change | Structural risk | ✅ causal + contagion |
| New shareholders / UBOs | Ownership KYC drift | ✅ contagion (PageRank) |
| Large funding round / expansion | Scale risk | ✅ velocity + causal (benign vs risk) |
| Dormant company activates | Suspicious activation | ⚠️ stability flags anomalous smoothness; no explicit dormancy signal |
| Legal entity name change | Re-KYC required | ❌ not implemented |
| Domain switch / website change | Business activity change | ❌ not implemented |
| Public business model pivot | Material business change | ❌ not implemented |

---

## Task List

Ordered by judging weight × demo impact. Check off as work is completed.

### 🔴 P0 — Compliance & Safety (20%)

- [x] **Wire audit log into drift pipeline** — `drift_customer_analyzed` and `drift_scan_completed` events now written via `AuditService` in `api/v1/drift.py` · `_score_to_level()` maps score to risk_level · payload includes velocity, tier, causal label, is_suspicious
- [ ] **Decision bar on drift page** — add `DecisionBar.tsx` to `frontend/src/app/drift/page.tsx`; extend `api/v1/decisions.py` to accept `customer_id: str` in addition to `case_id: UUID`

### 🔴 P0 — Cost Efficiency (20%)

- [ ] **At least one real T2 LLM call** — for T2 customers in `drift/service.py:scan()`, call `AnthropicClient` to adjudicate the causal vs benign hypothesis; without this the "96% savings" comparison is circular (the baseline LLM calls are also never made)

### 🟠 P1 — AI Quality (25%)

- [ ] **Fix BOCPD changepoint visual marker** — `bocpd_changepoint=False` is hardcoded at `service.py:296`; map `bocpd_changepoint_day` to the correct timeline index; add vertical dashed-line marker in `DriftTimeline.tsx`

### 🟠 P1 — Compliance & Safety (20%)

- [ ] **Add source citations to signal cards** — add `source_url` / `source_reference` field to `PublicSignalOut` in `drift/public_intel.py`; display in `TwoLayerPanel.tsx`; even a mock citation ("Reuters, 15 Jun 2026") satisfies the challenge requirement

### 🟠 P1 — Cost Efficiency (20%)

- [ ] **Track token usage per workflow** — add `tokens_used: int` and `model: str` to `CascadeCostReport` in `schemas/drift.py`; populate from `anthropic_client.py` response metadata when T2 calls are made

### 🟠 P1 — UX & Explainability (20%)

- [ ] **Resolve SHAP / per-layer claim** — option A (fast): reword README/docs to "per-layer contribution breakdown" and remove per-variable SHAP claim; option B (correct): route T1 drift customers through `RiskEngine.score_case`, attach SHAP values to `DriftCustomerDetail`

### 🟡 P2 — Engineering (15%)

- [ ] **Remove dead `if/pass` block** in `drift.py` (now gone from rfi handler — already fixed in this session)
- [ ] **Remove duplicate timeline endpoint** — `GET /drift/customers/{id}/timeline` returns identical payload to `GET /drift/customers/{id}`; differentiate or remove
- [ ] **Move 6 magic-number weights** from `service.py:104–163` to named constants in `core/config.py`
- [ ] **Add single-worker note** to `service.py:426` global singleton — unsafe under multi-process deployment
- [ ] **Frontend Dockerfile + compose** — backend Docker is production-quality; frontend has no Dockerfile; wire into `docker-compose.yml`

### 🟢 P3 — Engineering / Credibility

- [ ] **Add BOCPD unit test** — assert changepoint fires on a step-function series, does not fire on stationary noise
- [ ] **Qualify "real-time signals" language** in README and pitch — signals are simulated for MVP; architecture slots are ready for real feeds
- [ ] **Implement OpenSanctions slot-swap** — replace `generate_signals_for_customer()` headline templates with a real OpenSanctions API call; makes BR1 genuinely true

---

## Missing Use Cases — New Features Required

These three (S4, S5, S6) require new modules entirely:

- [ ] **S4 — Legal Entity Name Change Detection**
  - Signal source: corporate registries (ZEFIX, GLEIF, Companies House)
  - Detection: compare current registry name against KYC-captured name
  - Implementation: new signal type in `public_intel.py` + registry API client

- [ ] **S5 — Domain Switch / Website Content Monitoring**
  - Signal source: WHOIS, SecurityTrails, Wayback Machine, Firecrawl
  - Detection: domain registrar change; significant diff vs onboarding-era website
  - Implementation: new module `drift/domain_monitor.py` + Firecrawl integration

- [ ] **S6 — Business Model Pivot Detection**
  - Signal source: Crunchbase category changes, news ("pivot", "new direction"), website content diff
  - Detection: NLP classifier on website content diff vs onboarding description
  - Implementation: Crunchbase API client; extend causal hypothesis with business-model evidence type

---

## Public Intelligence — Fundamental Limitation

Every public signal is synthesized using headline templates in `public_intel.py`. No external API is called. The severity classifier is a 20-keyword lexicon.

The architecture and interfaces are correct — plugging in real feeds is a slot-swap. For the submission narrative, "real-time public signals" should be qualified as "simulated for the hackathon MVP."

### Challenge-specified integrations (slot-swap ready):

- [ ] **OpenSanctions** — aggregated OFAC + EU + UN; free tier available
- [ ] **GDELT Project** — free, near-real-time global news events
- [ ] **Swiss ZEFIX** — official Swiss commercial register; enables S4
- [ ] **GLEIF LEI Database** — global legal entity identifiers; ownership chain lookups
- [ ] **OpenCorporates** — beneficial ownership graph data
- [ ] **Crunchbase** — funding rounds, investors, company pivots; enables S6
- [ ] **Firecrawl** — OSS website-to-markdown scraping; enables S5 and S6
- [ ] **Wayback Machine** — free historical website snapshots; baseline for domain monitoring

---

## Code Quality — Should Fix

- [ ] **`service.py:104–163`** — 6 magic-number layer weights; move to named constants in `core/config.py`
- [ ] **`service.py:426`** — global mutable `_engine` singleton; add comment warning about multi-worker deployments
- [ ] **`service.py`** — `list_customers()` recomputes all 10 customers on every request; add short-lived TTL cache
- [ ] **`audit.py:138`** — `len(list(...all()))` loads entire table to count; replace with `COUNT(*)` query

---

## Post-Hackathon

- [ ] Alembic database migrations — critical before any schema change in production
- [ ] PostgreSQL migration — one env var change + swap `aiosqlite` → `asyncpg`
- [ ] GitHub Actions CI — lint (`ruff`), type check (`mypy`), test (`pytest`) on PRs
- [ ] Audit log frontend page — backend `GET /api/v1/audit` exists; no `/audit` frontend route
- [ ] Live alerts WebSocket — `ws/alerts` not implemented on either side
- [ ] Julius Baer model — `# TODO` in `ml/registry.py`
- [ ] Ripple XRPL model — `# TODO` in `ml/registry.py`
- [ ] Dark mode — design tokens exist in `tailwind.config.ts`; not implemented
- [ ] Mobile-responsive layout — desktop-only currently
- [ ] Production Docker profile — `docker-compose.yml` uses `--reload`; needs prod profile
- [ ] uv lockfile — `requirements.txt` uses `>=` ranges; generate `uv.lock` for reproducibility
