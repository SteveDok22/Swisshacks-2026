# Sentinel · Drift Engine — Roadmap

Current status: **core statistical engine is complete and production-quality; compliance loop, LLM integration, and 3 of 10 challenge use cases have critical gaps.**

Challenge: [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md)

---

## Judging Criteria — Honest Self-Assessment

| Criterion | Weight | Status | Notes |
|---|---|---|---|
| **AI Intelligence Quality** | 25% | ✅ Strong | 7 real algorithms, genuine causal separation, suspicious stability — differentiators most teams won't have |
| **Cost Efficiency** | 20% | ⚠️ Gap | 3-tier cascade is well-designed but T2 LLM calls are counted and never executed; token tracking exists in cost report but not per-workflow |
| **UX & Explainability** | 20% | ⚠️ Gap | 7 visualizations are solid; SHAP disconnected from drift pipeline; source citations missing from signal cards |
| **Compliance & Safety** | 20% | ⚠️ Gap | Anonymizer works; audit log never written from drift pipeline; HITL has no decision UI on drift page |
| **Engineering & Architecture** | 15% | ✅ Good | Modular 10-file engine, clean API, async throughout; no tests, no CI/CD |

---

## What Is Complete

### Statistical Core (all genuinely implemented)

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
| XGBoost + SHAP | Real — but wired to case management only, not drift |
| Audit service | Append-only, SQLite-persisted |
| Privacy / anonymizer | PII pseudonymized before Claude |
| Claude AI integration | Works for case explanations; not connected to drift |
| Jurisdiction rule packs | CH / EU / HK / AE all loaded |
| Docker | Backend Dockerfile is production-quality (multi-stage, non-root, healthcheck) |

### Challenge Use Case Coverage

| Use Case | Signal | Status |
|---|---|---|
| Negative news spike | Reputational risk | ✅ public_intel.py severity + Confirmation Lift |
| Cross-border transfer anomaly | Behavioural anomaly | ✅ BOCPD + velocity |
| Multiple entities + sudden flows | Structuring / layering | ✅ contagion + causal |
| Jurisdiction / legal form change | Structural risk | ✅ causal + contagion |
| New shareholders / UBOs | Ownership KYC drift | ✅ contagion (PageRank) |
| Large funding round / expansion | Scale risk | ✅ velocity + causal (benign vs risk) |
| Dormant company activates | Suspicious activation | ⚠️ stability detector flags anomalous smoothness; no explicit dormancy signal |
| Legal entity name change | Re-KYC required | ❌ not implemented |
| Domain switch / website change | Business activity change | ❌ not implemented |
| Public business model pivot | Material business change | ❌ not implemented |

---

## Critical Gaps — Fix Before Demo / Submission

### P0 — Audit log never written from Drift Engine

**Problem:** `AuditService.log()` is never called from `drift/service.py`. Every drift score produces zero audit entries. This directly contradicts BR6, the time-travel story, and the Compliance & Safety judging criterion (20%).

**Fix:** Call `audit.log(event_type="drift_scored", client_id=..., payload={score, layers, action})` at the end of `service.py:_analyze_customer()`. The service and DB table already exist — three-line change.

**Files:** `backend/app/drift/service.py`, `backend/app/services/audit.py`

---

### P0 — No human-in-the-loop on the Drift workspace

**Problem:** The drift page shows a verdict bar but has no decision-recording UI. The `/decisions` endpoint expects a `case_id` UUID; drift customers have string IDs. BR5 is unmet for the Drift Engine's entire workflow. Affects Compliance & Safety (20%) and UX (20%).

**Fix:**
- Add a decision bar to `frontend/src/app/drift/page.tsx` (mirrors existing `DecisionBar.tsx`)
- Extend the decisions endpoint to accept an optional `customer_id` string, or map drift customers to real `CaseDB` rows on first analysis

**Files:** `frontend/src/app/drift/page.tsx`, `backend/app/api/v1/decisions.py`

---

### P0 — T2 LLM reasoning counted but never executed

**Problem:** The cascade router identifies T2 customers and the cost report charges $0.05 per customer, but `DriftEngine.scan()` never calls Claude. The "96% savings vs LLM-on-everything" is accurate but the denominator LLM calls were also never made — the comparison is circular. Directly affects Cost Efficiency (20%).

**Fix:** For T2 customers in `service.py:scan()`, call `AnthropicClient` to adjudicate the causal vs benign hypothesis. One real LLM call per T2 customer makes the metric honest.

**Files:** `backend/app/drift/service.py`, `backend/app/services/anthropic_client.py`

---

### P1 — BOCPD changepoint never shown on timeline

**Problem:** `bocpd_changepoint=False` is hardcoded on every timeline point in `service.py:296`. The BOCPD runs, detects changepoints, stores the day — but the result is dropped before reaching the UI. No visual marker appears. This weakens the AI Intelligence Quality story (25%).

**Fix:**
- Map `bocpd_changepoint_day` to the correct timeline index, set `bocpd_changepoint=True` there
- Add a vertical dashed-line marker in `DriftTimeline.tsx`

**Files:** `backend/app/drift/service.py:296`, `frontend/src/components/drift/DriftTimeline.tsx`

---

### P1 — Source citations missing from signal cards

**Problem:** The challenge explicitly requires **source citations** as a model guardrail ("which news article, sanctions entry, or registry record drove the signal"). The Two-Layer Panel shows signal headlines but no links to sources. Affects Compliance & Safety (20%) and UX/Explainability (20%).

**Fix:** Add a `source_url` or `source_reference` field to the public signal schema. Even a mock citation ("Reuters, 15 Jun 2026") is better than nothing. Production slot: OpenSanctions IDs, GDELT event URLs.

**Files:** `backend/app/drift/public_intel.py`, `frontend/src/components/drift/TwoLayerPanel.tsx`

---

### P1 — Token usage not tracked per workflow

**Problem:** The cascade cost report tracks estimated dollar cost but not actual token counts per workflow. The challenge explicitly requires teams to "track token usage per workflow" and "estimate cost per 1,000 analyses."

**Fix:** Add `tokens_used: int` and `model: str` fields to `CascadeCostReport`. Populate from `anthropic_client.py` response metadata when T2 calls are made.

**Files:** `backend/app/drift/cascade.py`, `backend/app/schemas/drift.py`

---

### P1 — SHAP disconnected from Drift Engine

**Problem:** The drift score is a hand-coded weighted sum. SHAP only exists in the case management pipeline. No per-variable breakdown exists in the drift workspace.

**Options:**
- **A (fast, honest):** Rename the README/docs claim to "per-layer contribution breakdown" — which is real — and remove the per-variable SHAP claim
- **B (correct):** Route each T1 drift customer through `RiskEngine.score_case` and attach SHAP values to `DriftCustomerDetail`

**Files:** `backend/app/drift/service.py`, `README.md`, `docs/drift-engine.md`

---

## Code Quality — Should Fix

| Issue | Location | Fix |
|---|---|---|
| Dead `if/pass` block | `drift.py:115–116` | Delete it |
| Duplicate timeline endpoint | `drift.py:43–55` | Remove or differentiate |
| 6 magic-number weights | `service.py:104–163` | Move to `core/config.py` as named constants |
| Global mutable `_engine` singleton | `service.py:426` | Add comment noting multi-worker limitation |
| `list_customers()` recomputes on every request | `service.py` | Add short-lived TTL cache |
| Audit count uses `len(list(...all()))` | `audit.py:138` | Replace with `COUNT(*)` query |

---

## Public Intelligence — Fundamental Limitation

Every public signal is synthesized by `public_intel.py:generate_signals_for_customer()` using headline templates. No external API is called. The severity classifier is a 20-keyword lexicon.

The architecture and interfaces are correct — plugging in real feeds is a slot-swap. For the submission narrative, "real-time public signals" should be qualified as "simulated for the hackathon MVP."

### Challenge-specified integrations to implement (slot-swap ready):

| Category | Recommended tool | Why |
|---|---|---|
| Sanctions | **OpenSanctions** | Aggregated OFAC + EU + UN in one API; recommended by challenge |
| News | **GDELT Project** | Free, near-real-time, global coverage |
| Corporate registry | **Swiss ZEFIX** | Official Swiss register — directly relevant for FINMA context |
| Corporate registry | **GLEIF LEI Database** | Global legal entity identifiers — ownership chain lookups |
| Ownership | **OpenCorporates** | Beneficial ownership graph data |
| Funding | **Crunchbase** | Challenge's primary recommendation for funding intelligence |
| Domain monitoring | **Firecrawl** | OSS, website-to-markdown; enables S5 and S6 use cases |
| Domain history | **Wayback Machine** | Free, historical website snapshots for baseline |

---

## Missing Use Cases — New Features Required

These three challenge use cases (S4, S5, S6) require new modules entirely:

### S4 — Legal Entity Name Change Detection
- **Signal source:** Corporate registries (ZEFIX, Companies House, GLEIF)
- **Detection:** Compare current registry name against KYC-captured name
- **Action:** Trigger KYC refresh; re-evaluate risk category
- **Implementation:** New signal type in `public_intel.py`; registry API client

### S5 — Domain Switch / Website Content Monitoring
- **Signal source:** WHOIS (ICANN), SecurityTrails, Wayback Machine, Firecrawl
- **Detection:** Domain registrar change, significant diff between current and onboarding-era website content
- **Action:** Re-analyse website; compare vs onboarding data
- **Implementation:** New module `drift/domain_monitor.py`; Firecrawl or Diffbot integration

### S6 — Business Model Pivot Detection
- **Signal source:** Crunchbase (category changes), news (keyword: "pivot", "new direction"), website content diff
- **Detection:** Company category change in Crunchbase; NLP classifier on website content diff
- **Action:** Update risk classification; escalate for compliance
- **Implementation:** Crunchbase API client; extend causal hypothesis with "business model change" evidence type

---

## Not Started — Post-Hackathon

| Feature | Notes |
|---|---|
| Real API integrations | OpenSanctions, GDELT, GLEIF, ZEFIX, OpenCorporates, Crunchbase, Firecrawl |
| Domain monitoring module | `drift/domain_monitor.py` — enables S5 + S6 use cases |
| Alembic database migrations | Critical before any schema change in production |
| PostgreSQL migration | One env var change + swap `aiosqlite` → `asyncpg` |
| Frontend Dockerfile + compose | Backend Docker is complete; frontend has no Dockerfile |
| Tests | `backend/tests/` is empty; pytest infrastructure is already in dev deps |
| GitHub Actions CI | Lint (`ruff`), type check (`mypy`), test (`pytest`) on PRs |
| Audit log frontend page | Backend `GET /api/v1/audit` exists; no `/audit` frontend route |
| Live alerts WebSocket | `ws/alerts` — not implemented on either side |
| Julius Baer model | `# TODO` in `ml/registry.py` |
| Ripple XRPL model | `# TODO` in `ml/registry.py` |
| Dark mode | Design tokens in `tailwind.config.ts`; not implemented |
| Mobile-responsive layout | Desktop-only currently |
| Production Docker profile | Current `docker-compose.yml` uses `--reload`; no prod profile |
| uv lockfile | `requirements.txt` uses `>=` ranges; generate `uv.lock` for reproducibility |

---

## Priority Order for Remaining Hackathon Time

Ordered by judging weight and demo impact.

| Priority | Item | Effort | Judging criterion |
|---|---|---|---|
| 🔴 P0 | Wire audit log into drift pipeline | 30 min | Compliance & Safety (20%) |
| 🔴 P0 | Decision bar on drift page | 2–3 h | Compliance & Safety (20%) + UX (20%) |
| 🔴 P0 | At least one real T2 LLM call | 1–2 h | Cost Efficiency (20%) |
| 🟠 P1 | Fix BOCPD changepoint visual marker | 1 h | AI Quality (25%) |
| 🟠 P1 | Add source citations to signal cards | 1 h | Compliance & Safety (20%) |
| 🟠 P1 | Add token count to cost report | 30 min | Cost Efficiency (20%) |
| 🟠 P1 | Resolve SHAP claim (fix or reword docs) | 30 min | UX & Explainability (20%) |
| 🟡 P2 | Move magic weights to config | 1 h | Engineering (15%) |
| 🟡 P2 | Remove dead `if/pass` block in RFI | 15 min | Engineering (15%) |
| 🟡 P2 | Remove duplicate timeline endpoint | 15 min | Engineering (15%) |
| 🟡 P2 | Frontend Dockerfile + docker-compose wire-up | 1 h | Engineering (15%) |
| 🟢 P3 | Add BOCPD unit test | 1 h | Engineering (15%) |
| 🟢 P3 | Qualify "real-time signals" language in docs | 15 min | Credibility in Q&A |
| 🟢 P3 | Implement OpenSanctions slot-swap | 2 h | AI Quality (25%) — makes BR1 real |
