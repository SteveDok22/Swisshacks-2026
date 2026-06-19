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

## Tests

**Stack:** plain `pytest` for unit tests + `pytest-bdd` for scenario/integration tests.  
`pytest` and `pytest-asyncio` are already in dev deps (`pyproject.toml`). Add `pytest-bdd` for Gherkin feature files.

BDD is a natural fit here: the 7 synthetic scenarios and H1–H4 hypotheses are already written in plain English, domain language is rich (KYC drift, suspicious stability), and judges / compliance officers can read Gherkin feature files directly.

### Why two layers

| Layer | Tool | What it covers |
|---|---|---|
| Unit | `pytest` | Pure functions — math, helpers, converters — no I/O |
| Scenario / integration | `pytest-bdd` | End-to-end engine behavior, API contracts, compliance rules expressed as readable Gherkin |

---

### 🟠 P1 — Unit tests (pure functions, no I/O)

- [ ] **`test_bocpd.py`** — assert changepoint fires on a step-function series; does not fire on stationary noise; BOCPD is online (no future data used)
- [ ] **`test_velocity.py`** — KL divergence is zero for identical distributions; increases monotonically as mean shifts; velocity is positive after a step change
- [ ] **`test_causal.py`** — risk-shaped signature (volume up + margin collapses + dirty counterparties) produces `label="risk"`; benign signature (volume up + margin preserved + clean counterparties) produces `label="benign"`
- [ ] **`test_stability.py`** — flat customer in volatile cohort is flagged `is_suspicious=True`; genuinely volatile customer is not
- [ ] **`test_cascade.py`** — score < 40 routes to T0; 40 ≤ score < 70 routes to T1; score ≥ 70 routes to T2; cumulative cost accounting is correct
- [ ] **`test_score_to_level.py`** — `_score_to_level` thresholds match `RiskLevel` enum exactly (boundary values: 0, 30, 31, 60, 61, 85, 86, 100)

---

### 🟠 P1 — BDD scenario tests (Gherkin feature files)

Add `pytest-bdd` to dev deps: `"pytest-bdd>=7.0.0"` in `pyproject.toml`.  
Feature files live in `backend/tests/features/`; step definitions in `backend/tests/steps/`.

- [ ] **`drift_detection.feature`** — the 7 synthetic scenarios with ground truth labels:

  ```gherkin
  Feature: KYC Drift Detection

    Scenario: Volume creep raises drift score above review threshold
      Given a customer with monthly volume growing 8% per month for 18 months
      When the drift engine analyses the customer
      Then the drift score exceeds 40
      And the velocity band is "notable" or higher
      And the causal label is "risk"

    Scenario: Benign expansion is not escalated
      Given a customer with a clean funding round and stable margins
      When the drift engine analyses the customer
      Then the causal label is "benign"
      And the drift score is below 40

    Scenario: Slow-walker is flagged despite low absolute drift
      Given a customer with near-zero volume variance for 24 months
      And the customer's cohort has high volatility
      When the drift engine analyses the customer
      Then is_suspicious is true
      And the drift score is elevated above 50
  ```

- [ ] **`contagion.feature`** — ownership risk propagation:

  ```gherkin
  Feature: Ownership Contagion

    Scenario: Direct owner of sanctioned entity is elevated
      Given a sanctioned seed entity
      And a customer who directly owns the sanctioned entity
      When contagion is propagated
      Then the customer's propagated_risk exceeds 0.1

    Scenario: Third-degree connection is not elevated
      Given a sanctioned seed entity
      And a customer three ownership hops away
      When contagion is propagated
      Then the customer's propagated_risk is below 0.05
  ```

- [ ] **`time_travel.feature`** — no look-ahead bias:

  ```gherkin
  Feature: Time-Travel Audit

    Scenario: Replay uses only data available at the as-of date
      Given a customer whose sanctions event occurs at month 18
      When the engine replays the customer as-of month 12
      Then no public signals after month 12 are included
      And no contagion edges listed after month 12 are included
      And the as-of score is lower than the current score

    Scenario: Early detection lead time is positive
      Given a customer flagged at month 14 with sanctions at month 18
      When lead_time_months is computed
      Then lead_time_months equals 4
  ```

- [ ] **`audit_compliance.feature`** — compliance backbone:

  ```gherkin
  Feature: Audit Log Compliance

    Scenario: Drift analysis always produces an audit entry
      Given the drift engine is running
      When an officer requests the full analysis for any customer
      Then an audit entry with event_type "drift_customer_analyzed" exists
      And the entry contains the customer's drift_score
      And the entry contains the risk_level

    Scenario: Audit log is append-only
      Given an existing audit entry
      When the audit service is called
      Then no update or delete method exists on AuditService
  ```

- [ ] **`api_contract.feature`** — API smoke tests using `httpx.AsyncClient`:

  ```gherkin
  Feature: API Contract

    Scenario: Customer list is sorted by drift score descending
      When I call GET /api/v1/drift/customers
      Then the response is 200
      And each customer's drift_score is >= the next customer's drift_score

    Scenario: Unknown customer returns 404
      When I call GET /api/v1/drift/customers/nonexistent-id
      Then the response status is 404

    Scenario: Cascade scan returns cost report
      When I call POST /api/v1/drift/scan
      Then the response is 200
      And savings_pct is between 0 and 100
      And total_customers equals 10
  ```

---

### 🟢 P3 — Hypothesis validation tests

These are the H1–H4 claims from the README — make them machine-verifiable:

- [ ] **`test_hypothesis_h1.py`** — run full engine on all 7 scenarios; assert BOCPD lead time ≥ 2 months on drifting scenarios; assert 0 false positives on `stable` scenario
- [ ] **`test_hypothesis_h2.py`** — assert velocity alert fires earlier than absolute-threshold alert at equal false-positive rate
- [ ] **`test_hypothesis_h3.py`** — assert 2-hop contagion customers are elevated; assert 3+ hop customers are not
- [ ] **`test_hypothesis_h4.py`** — assert cascade cost < 10% of LLM-on-everything cost; assert high-risk recall is unchanged

---

## Post-Hackathon

- [ ] Alembic database migrations — critical before any schema change in production
- [ ] PostgreSQL migration — one env var change + swap `aiosqlite` → `asyncpg`
- [ ] GitHub Actions CI — lint (`ruff`), type check (`mypy`), test (`pytest --bdd`) on PRs
- [ ] Audit log frontend page — backend `GET /api/v1/audit` exists; no `/audit` frontend route
- [ ] Live alerts WebSocket — `ws/alerts` not implemented on either side
- [ ] Julius Baer model — `# TODO` in `ml/registry.py`
- [ ] Ripple XRPL model — `# TODO` in `ml/registry.py`
- [ ] Dark mode — design tokens exist in `tailwind.config.ts`; not implemented
- [ ] Mobile-responsive layout — desktop-only currently
- [ ] Production Docker profile — `docker-compose.yml` uses `--reload`; needs prod profile
- [ ] uv lockfile — `requirements.txt` uses `>=` ranges; generate `uv.lock` for reproducibility
