# Sentinel · Drift Engine — Roadmap

Current status: **core statistical engine complete; 1 use case genuinely works on synthetic data, 5 are partial/indirect, 3 are missing entirely.**

> Audit verified 2026-06-20 against actual code (Sentinel_UseCase_Audit.pdf). Three groups: A — Works (case 2), B — Partial/Indirect (cases 1, 3, 4, 5, 6, 7), C — Missing (cases 8, 9, 10).

Challenge: [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md)

---

## Judging Criteria — Honest Self-Assessment

| Criterion | Weight | Status | Notes |
|---|---|---|---|
| **AI Intelligence Quality** | 25% | ✅ Strong | 7 real algorithms, genuine causal separation, suspicious stability |
| **Cost Efficiency** | 20% | ⚠️ Partial | Cascade executes T2 LLM adjudications and reports actual real/mock calls; no per-workflow token count |
| **UX & Explainability** | 20% | ⚠️ Gap | 7 visualisations solid; SHAP disconnected from drift; source citations missing |
| **Compliance & Safety** | 20% | ⚠️ Gap | Anonymizer works; ~~audit log not written from drift~~ fixed; HITL missing on drift page |
| **Engineering & Architecture** | 15% | ✅ Good | Modular 10-file engine, clean API, async throughout; unit + BDD tests added; no CI/CD |

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
| Claude AI integration | Works for case explanations and T2 drift adjudication; mock mode works without an API key |
| Jurisdiction rule packs | CH / EU / HK / AE all loaded |
| Docker | Backend Dockerfile production-quality (multi-stage, non-root, healthcheck) |

### Challenge Use Case Coverage

Statuses from code-verified audit (2026-06-20). Legend: ✅ WORKS · ⚠️ PARTIAL · 🔶 INDIRECT · ❌ MISSING

| # | Use Case | Signal | Status | What exists | Real sources needed | Demo data |
|---|---|---|---|---|---|---|
| 1 | Negative news spike | Reputational risk | ⚠️ PARTIAL | Lexicon classifier + confirmation lift; no live feed, no spike detection | EventRegistry / NewsAPI.ai, GDELT, Google News RSS | Wirecard: adverse media, whistle-blower allegations, accounting concerns, and AML red flags accumulate before collapse |
| 2 | Cross-border transfer anomaly | Behavioural anomaly | ✅ WORKS | BOCPD + velocity on synthetic data | Internal transactions, OpenSanctions (geography) ||
| 3 | Multiple entities + sudden flows | Structuring / layering | ⚠️ PARTIAL | Contagion + causal; no named layering detector | GLEIF, OpenCorporates, Companies House, internal tx graph | Danske Estonia: linked shell-company customers, weak documentation, hidden beneficial ownership, and large suspicious flows |
| 4 | Jurisdiction / legal form change | Structural risk | 🔶 INDIRECT | `jurisdiction.py` is rule-pack selector, not a change detector | ZEFIX, GLEIF, OpenCorporates, Companies House | Long Blockchain: Long Island Iced Tea changed its name to Long Blockchain, triggering a clear re-KYC and identity-change signal |
| 5 | New shareholders / UBOs | Ownership KYC drift | ⚠️ PARTIAL | PageRank over synthetic graph; no real UBO lookup | Companies House PSC, OpenCorporates, GLEIF, OpenSanctions |
| 6 | Large funding round / expansion | Scale risk | ⚠️ PARTIAL | `funding_event` template + causal; no live feed | EventRegistry / NewsAPI.ai, GDELT, Crunchbase, company website | 
| 7 | Dormant company activates | Suspicious activation | ⚠️ PARTIAL | Stability flags smoothness; no explicit zero→volume-jump detector | Internal transactions, ZEFIX, OpenCorporates, Companies House | 
| 8 | Legal entity name change | Re-KYC required | ❌ MISSING | Not implemented; no registry integration | ZEFIX, GLEIF, RDAP/WHOIS, EventRegistry/GDELT | 
| 9 | Domain switch / website change | Business activity change | ❌ MISSING | Not implemented; no WHOIS/Wayback/Firecrawl | RDAP/WHOIS, Wayback Machine, Firecrawl, EventRegistry | N26 scale-risk change: rapid funding, customer growth, international expansion, and monitoring deficiencies made the original risk profile outdated |
| 10 | Public business model pivot | Material business change | ❌ MISSING | Not implemented; no business model comparison | EventRegistry/GDELT, ZEFIX, GLEIF, Wayback Machine, Firecrawl |

---

## Task List

Ordered by judging weight × demo impact. Check off as work is completed.

### 🔴 P0 — Compliance & Safety (20%)

- [x] **Wire audit log into drift pipeline** — 5 compliance-relevant endpoints now audited in `api/v1/drift.py`: `drift_customer_analyzed` · `drift_scan_completed` · `drift_replay_executed` · `drift_scenario_injected` · `drift_rfi_generated` · `_score_to_level()` maps score to risk_level · list/timeline/contagion intentionally unaudited (read-only browsing)
- [ ] **Decision bar on drift page** — add `DecisionBar.tsx` to `frontend/src/app/drift/page.tsx`; extend `api/v1/decisions.py` to accept `customer_id: str` in addition to `case_id: UUID`

### 🔴 P0 — Cost Efficiency (20%)

- [x] **Actual T2 LLM adjudication path** — for T2 customers in `drift/service.py:scan()`, call `AnthropicClient` to adjudicate risk-shaped vs benign vs ambiguous hypotheses; report actual real/mock calls and parsed adjudications. The LLM-on-everything baseline remains a counterfactual cost estimate.

### 🟠 P1 — AI Quality (25%)

- [ ] **Case 7: Dormancy-break detector** — highest value-for-effort quick win (no external API needed). The stability engine + volume time-series already exist. Add explicit `near-zero baseline → volume jump` detector (~30 lines + 1 test) in `drift/stability.py` or new `drift/dormancy.py`; wire signal into `drift/service.py`. Moves Case 7 from PARTIAL → WORKS; yields a genuine new flag worth 25% of score.
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

- [x] **Add BOCPD unit test** — assert changepoint fires on a step-function series, does not fire on stationary noise (covered by `test_bocpd.py`)
- [ ] **Qualify "real-time signals" language** in README and pitch — signals are simulated for MVP; architecture slots are ready for real feeds
- [ ] **Implement OpenSanctions slot-swap** — replace `generate_signals_for_customer()` headline templates with a real OpenSanctions API call; makes BR1 genuinely true

---

## Real Source Integration — Pipeline Architecture

All real-source use cases follow the same pattern:

```
Source A ──→ fetch + parse ──→ signal_A (severity 0–1) ──┐
Source B ──→ fetch + parse ──→ signal_B (severity 0–1) ──┤──→ XGBoost fusion ──→ risk level
Source C ──→ fetch + parse ──→ signal_C (severity 0–1) ──┘         ↓
                                                              SHAP explains
                                                          which source drove it
```

Each source gets its own adapter in `sources/`. Signal fusion runs through the existing `RiskEngine`. BOCPD wraps time-series sources for drift vs. one-off detection.

**EventRegistry / NewsAPI.ai note**: EventRegistry groups 20–50 articles from different media into a single `Event` object. This means spike detection works on event-level aggregation, not raw article count — much more robust signal for use cases 1, 6, 10.

---

## Missing & Partial Use Cases — Implementation Plan

### Sprint 0 — Zero dependencies (~1–2 hours)

- [ ] **Case 7: Dormancy-break detector** (see P1 task above) — closes without any external API

---

### Sprint 1 — Registry sources: Cases 4, 5, 8 (ZEFIX / GLEIF / OpenCorporates)

Cases 4, 5, 8 share the same fetch-diff-score pattern. Build one generic `RegistryAdapter` base class, then plug in per-source implementations.

- [ ] **Case 8 — Legal entity name change**
  - Sources: ZEFIX (Swiss), GLEIF (global LEI), RDAP/WHOIS (domain), EventRegistry/GDELT (public news about rename)
  - Detection: fetch current legal name → diff vs. KYC baseline → `name_changed` signal
  - Implementation: `sources/zefix.py`, `sources/gleif.py`; new signal type in `public_intel.py`

- [ ] **Case 5 — New shareholders / UBOs** (upgrade from PARTIAL)
  - Sources: Companies House PSC (UK persons of significant control), OpenCorporates (directors/officers), GLEIF (parent-child), OpenSanctions (screen new owners)
  - Detection: pull current UBO list → diff vs. stored baseline → screen each new owner → `owner_on_watchlist` signal
  - Implementation: `sources/companies_house.py`, `sources/opensanctions.py`; replace synthetic PageRank seed with real data

- [ ] **Case 4 — Jurisdiction / legal form change** (upgrade from INDIRECT)
  - Sources: ZEFIX, GLEIF, OpenCorporates, Companies House
  - Detection: compare current legal form + jurisdiction vs. onboarding baseline → `jurisdiction_risk_delta` signal
  - Implementation: extend `jurisdiction.py` from rule-pack selector to change detector

---

### Sprint 2 — News & media sources: Cases 1, 6, 10 (EventRegistry / GDELT)

- [ ] **Case 1 — Negative news spike** (upgrade from PARTIAL)
  - Sources: EventRegistry / NewsAPI.ai (primary — event-level aggregation), GDELT (open global events), Google News RSS (simple fallback)
  - Detection: rolling window event count per entity → spike = count > baseline + 2σ over 7 days
  - Implementation: `sources/event_registry.py`; replace `public_intel.py` headline templates with real event fetch; add `spike_score` time-series to BOCPD

- [ ] **Case 6 — Large funding round / expansion** (upgrade from PARTIAL)
  - Sources: EventRegistry / NewsAPI.ai (funding news events), GDELT, Crunchbase (funding rounds + investors), company website (official announcements)
  - Detection: funding event detected → cross-reference amount vs. typical AUM → `scale_jump_ratio` signal
  - Implementation: `sources/crunchbase.py`; extend `funding_event` template to real Crunchbase API call

- [ ] **Case 10 — Public business model pivot**
  - Sources: EventRegistry / GDELT (pivot/direction news), ZEFIX / GLEIF (category change), Wayback Machine (historical website), Firecrawl (current website content)
  - Detection: embed onboarding business description vs. current website/news → cosine drift score via sentence-transformers
  - Implementation: `sources/firecrawl.py`, `sources/wayback.py`; new `drift/business_model.py` embedding comparator

---

### Sprint 3 — Web monitoring: Case 9 (WHOIS / Wayback / Firecrawl)

- [ ] **Case 9 — Domain switch / website change**
  - Sources: RDAP/WHOIS (domain registrar + age), Wayback Machine (historical snapshots), Firecrawl (current content scrape), EventRegistry/GDELT (news about domain change)
  - Detection: domain registrar diff + sentence-transformer similarity (onboarding snapshot vs. current) → `content_drift_score`
  - Implementation: `sources/whois.py`, `sources/wayback.py`, `sources/firecrawl.py`; new module `drift/domain_monitor.py`

---

### Source → Use Case matrix

| Source | Cases |
|---|---|
| EventRegistry / NewsAPI.ai | 1, 6, 8, 10 |
| GDELT | 1, 6, 8, 10 |
| Google News RSS | 1 (fallback) |
| ZEFIX | 4, 7, 8, 10 |
| GLEIF | 3, 4, 5, 8, 10 |
| OpenCorporates | 3, 4, 5, 7 |
| Companies House PSC | 3, 5, 7 |
| OpenSanctions | 2, 5 |
| Crunchbase | 6 |
| RDAP/WHOIS | 8, 9 |
| Wayback Machine | 9, 10 |
| Firecrawl | 9, 10 |
| Internal transactions | 2, 3, 7 |

---

## Public Intelligence — Fundamental Limitation

Every public signal is synthesized using headline templates in `public_intel.py`. No external API is called. The severity classifier is a 20-keyword lexicon.

The architecture and interfaces are correct — plugging in real feeds is a slot-swap. For the submission narrative, "real-time public signals" should be qualified as "simulated for the hackathon MVP."

### Challenge-specified integrations (slot-swap ready):

- [ ] **EventRegistry / NewsAPI.ai** — event-level news aggregation (20–50 articles per story); primary for cases 1, 6, 8, 10
- [ ] **GDELT Project** — free, near-real-time global news events; fallback for cases 1, 6, 10
- [ ] **Google News RSS** — simple per-entity news feed; lightweight fallback for case 1
- [ ] **OpenSanctions** — aggregated OFAC + EU + UN; free tier; primary for case 5 UBO screening
- [ ] **Swiss ZEFIX** — official Swiss commercial register; cases 4, 7, 8, 10
- [ ] **GLEIF LEI Database** — global legal entity identifiers; ownership chain lookups; cases 3, 4, 5, 8, 10
- [ ] **OpenCorporates** — international registry aggregator; directors/officers/relationships; cases 3, 4, 5, 7
- [ ] **Companies House PSC** — UK persons of significant control; cases 3, 5, 7
- [ ] **Crunchbase** — funding rounds, investors, company pivots; case 6
- [ ] **RDAP/WHOIS** — domain registrar and registration age; cases 8, 9
- [ ] **Firecrawl** — OSS website-to-markdown scraping; cases 9, 10
- [ ] **Wayback Machine** — free historical website snapshots; baseline for domain/content monitoring; cases 9, 10

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

- [x] **`test_bocpd.py`** — changepoint fires on step series; silent on stationary noise; online property; `standardize` behavior — 6 tests
- [x] **`test_velocity.py`** — KL divergence zero for identical distributions; monotonically increasing with mean shift; velocity positive after step; `velocity_band` bands; mismatched metric lengths raises — 10 tests
- [x] **`test_causal.py`** — risk signature → `label="risk"`; benign signature → `label="benign"`; p_risk in [0,1]; contributions cover all dimensions; end-to-end with simulator — 8 tests
- [x] **`test_stability.py`** — flat customer in volatile cohort → `is_suspicious=True`; volatile customer → not suspicious; quiet environment does not flag; `cohort_volatility` behavior — 11 tests
- [x] **`test_cascade.py`** — score < 30 → T0; 30–55 → T1; ≥55 + value → T2; sanctions + value → T2; cumulative cost ordering — 11 tests (actual thresholds: t1=30, t2=55)
- [x] **`test_drift_t2_llm.py`** — scan calls LLM only for T2 customers; zero-T2 scan performs zero calls; invalid LLM JSON returns safe fallback.
- [x] **`test_contagion.py`** — direct neighbor elevated > 0.1; near > far; hop counts; cytoscape shape; empty seeds — 11 tests
- [x] **`test_score_boundaries.py`** — `score_to_level` / `score_to_action` full boundary coverage incl. float regression — 15 tests (previously `test_score_to_level`)

---

### 🟠 P1 — BDD scenario tests (Gherkin feature files)

Add `pytest-bdd` to dev deps: `"pytest-bdd>=7.0.0"` in `pyproject.toml`. ✅ Added.
Feature files live in `backend/tests/features/`; step definitions in `backend/tests/test_*_bdd.py`.

- [x] **`drift_detection.feature`** — 3 scenarios with ground truth labels (benign_expansion, combined/risk, suspicious_stability slow-walker):

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

- [x] **`contagion.feature`** — ownership risk propagation:

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

- [ ] **`time_travel.feature`** — no look-ahead bias (not yet implemented — requires more complex fixture setup):

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

- [x] **`audit_compliance.feature`** — compliance backbone:

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

- [x] **`api_contract.feature`** — API smoke tests using `httpx.AsyncClient`:

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
