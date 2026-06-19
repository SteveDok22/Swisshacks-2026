# Sentinel · Drift Engine — Roadmap

Current status: **core statistical engine is complete and production-quality; compliance loop and LLM integration have critical gaps that a technical reviewer will notice.**

---

## What Is Complete

### Statistical Core (all genuinely implemented, not stubs)

| Component | File | Notes |
|---|---|---|
| Bayesian Online Changepoint Detection | `drift/bocpd.py` | Adams & MacKay 2007, Normal-Inverse-Gamma priors, Student-t predictive |
| KL Divergence + Drift Velocity | `drift/velocity.py` | Closed-form Gaussian KL, smoothed first-differencing, velocity + acceleration |
| Ownership Contagion | `drift/contagion.py` | Real NetworkX PageRank, personalization vector on seed nodes, hop-distance computation |
| Causal Drift (LLR test) | `drift/causal.py` | Neyman-Pearson likelihood-ratio between risk and benign hypotheses |
| Suspicious Stability | `drift/stability.py` | Multiplicative CV × environmental movement formulation |
| Cost-Aware Cascade | `drift/cascade.py` | Correct cumulative-cost accounting (T2 customer pays T0+T1+T2) |
| Time-Travel Audit | `drift/timetravel.py` | Future data correctly truncated in all three sources: behavioral windows, public signals, contagion edges |
| Drift Engine Orchestrator | `drift/service.py` | All 7 layers wired, two-layer fusion, confirmation lift, causal modulation, stability elevation |
| Synthetic Book | `drift/simulator.py` | 7 scenarios with explicit ground truth, causal/benign discriminators are internally consistent |

### Platform

| Area | Status |
|---|---|
| REST API | 27 endpoints, all functional |
| Frontend — 7 drift visualizations | All render real API data (radar, timeline, causal, two-layer, contagion, stability, time-travel) |
| XGBoost + SHAP | Trained and real — but only wired to the case-management system, not the Drift Engine (see gaps) |
| Audit service | Genuinely append-only — no update/delete methods; SQLite-persisted |
| Officer decision recording | Override detection, mandatory rationale on overrides, case status update, audit logged |
| Privacy / anonymizer | PII pseudonymized before Claude; FINMA Circular 2024/3 compliant |
| Claude AI integration | Works for case explanations; not yet connected to the Drift Engine |
| Jurisdiction rule packs | CH / EU / HK / AE all loaded and toggleable |

---

## Critical Gaps — Fix Before Demo / Submission

These are the items a technical judge reading the code will notice. They are also the items where the README's claims and the code diverge most visibly.

### 1. Audit log is never written from the Drift Engine

**Problem:** `AuditService.log()` is called from the case-management pipeline but never from `DriftEngine._analyze_customer()` or `scan()`. Drift scores produce zero audit entries. This directly contradicts BR6 and the time-travel audit story.

**Fix:** Call `audit.log(event_type="drift_scored", client_id=..., payload={score, layers, action})` at the end of `service.py:_analyze_customer()`. The service and DB table already exist — it is a three-line change.

**Files:** `backend/app/drift/service.py`, `backend/app/services/audit.py`

---

### 2. No human-in-the-loop on the Drift workspace

**Problem:** The drift page shows a recommended action (verdict bar) but has no way for an officer to record a decision, override the AI, or add a rationale. The `/decisions` endpoint expects a `case_id` UUID — drift customers have string IDs (`"drift-004"`). BR5 is unmet for the Drift Engine's primary workflow.

**Fix:**
- Add a decision bar component to `frontend/src/app/drift/page.tsx` (mirrors `DecisionBar.tsx` already used in the case workspace)
- Either map drift customers to real `CaseDB` rows on first analysis, or extend the decisions endpoint to accept an optional `customer_id` string

**Files:** `frontend/src/app/drift/page.tsx`, `backend/app/api/v1/decisions.py`

---

### 3. T2 LLM reasoning is counted but never executed

**Problem:** The cascade router correctly identifies T2 customers and the cost report charges them `$0.05`. But `DriftEngine.scan()` never calls Claude for these customers. The "96% savings vs LLM-on-everything" is technically correct but the denominator calls were also never made — the comparison is circular.

**Fix:** For T2 customers in `cascade.py` or `service.py:scan()`, call `AnthropicClient` with a prompt asking it to adjudicate the causal vs benign hypothesis. Even one real LLM call per T2 customer makes the metric honest.

**Files:** `backend/app/drift/cascade.py`, `backend/app/drift/service.py`, `backend/app/services/anthropic_client.py`

---

### 4. BOCPD changepoint is never shown on the timeline

**Problem:** `_analyze_customer()` runs BOCPD and stores `bocpd_changepoint_day` in the detail object, but `bocpd_changepoint=False` is hardcoded for every point in the timeline array (service.py line 296). The frontend `DriftTimeline` component has no code to render a changepoint marker. The detection happens; its result is dropped before reaching the UI.

**Fix:**
- Map `bocpd_changepoint_day` to the correct index in the timeline array and set `bocpd_changepoint=True` for that point
- In `DriftTimeline.tsx`, add a vertical marker (e.g., dashed line) at points where `bocpd_changepoint === true`

**Files:** `backend/app/drift/service.py` line 296, `frontend/src/components/drift/DriftTimeline.tsx`

---

### 5. SHAP is disconnected from the Drift Engine

**Problem:** The README states "Per-variable SHAP values: which KYC fields or transaction corridors most influenced the score?" SHAP only exists in the case-management pipeline (`RiskEngine.score_case`). The drift score is a hand-coded weighted sum — SHAP cannot be applied to it directly. There is no per-variable breakdown in the drift workspace.

**Options (choose one):**
- A. Route each drift customer through `RiskEngine.score_case` at T1 tier and attach the resulting SHAP values to `DriftCustomerDetail`
- B. Replace the magic-weight formula with an XGBoost model trained on the 7-layer features, then run SHAP on that model's output
- C. Rename the claim in README/docs to "per-layer contribution breakdown" (which is real) and remove the per-variable SHAP claim

Option C is the fastest honest fix; options A or B make the claim true.

**Files:** `backend/app/drift/service.py`, `README.md`, `docs/drift-engine.md`

---

## Code Quality — Should Fix

These do not break demos but will cause embarrassment if a judge reads the code.

### Dead code in RFI endpoint

`backend/app/api/v1/drift.py` lines 115–116:
```python
if detail.propagated_risk if hasattr(detail, "propagated_risk") else 0:
    pass
```
Vacuous conditional that does nothing. `DriftCustomerDetail` always has `propagated_risk`. Delete it and wire contagion risk into the RFI question selection.

### Timeline endpoint is a full duplicate

`GET /drift/customers/{id}/timeline` has the same function body and return type as `GET /drift/customers/{id}`. If the intent is to return only the timeline field, slice the response. If there is no difference, remove the duplicate route.

**File:** `backend/app/api/v1/drift.py` lines 43–55

### Six magic-number weights in the score formula

`service.py` contains hardcoded saturation constants and fusion weights:
- `min(max_velocity / 3.0, 1.0)` — velocity saturation
- `min(final_drift / 20.0, 1.0)` — drift saturation
- `0.6 * vel_norm + 0.25 * drift_norm + 0.4 * prop_risk` — fusion weights
- `1.0 + min((lift - 1.0) / 3.0, 1.0) * 0.35` — confirmation lift amplification
- `0.45 + 0.55 * causal.p_risk` — causal modulation range
- `max(score, 50.0 + stability.suspicion * 40.0)` — stability floor

Move these to `core/config.py` as named, documented constants so they can be tuned without touching business logic.

### Global mutable DriftEngine singleton

`get_drift_engine()` uses a module-level `_engine` variable. `inject_scenario()` mutates `self._book` in place. In a multi-worker uvicorn deployment this desyncs workers. For a hackathon demo this is acceptable, but the comment should note the limitation.

**File:** `backend/app/drift/service.py`

### No caching on `list_customers()`

Every `GET /drift/customers` call re-runs full analysis for all 15 customers. The README claims the system scales to "thousands of customers." Add an in-request cache or a short-lived TTL cache keyed on book version.

---

## Public Intelligence (BR1) — Fundamental Limitation

Every public signal is generated by `public_intel.py:generate_signals_for_customer()` using headline templates and the customer's first name. No external API is called. The severity classifier is a 20-entry keyword lexicon.

This is a known, explicit limitation (the module's docstring acknowledges it). The architecture and interfaces are correct — plugging in real feeds is a slot-swap. But for the submission narrative, the phrase "real-time public signals" should be qualified with "simulated for the hackathon MVP; production slot takes an embedding classifier and live feeds (OFAC, Refinitiv, GDELT)."

**Realistic integrations to mention:**
- OFAC SDN list (free, REST API)
- EU Consolidated Sanctions list (free XML)
- GDELT Project news events (free, near real-time)
- OpenCorporates for ownership graph (freemium)

---

## Not Started — Post-Hackathon / Future

| Feature | Notes |
|---|---|
| Real sanctions API integration | Architecture ready; slot in `public_intel.py` |
| Tests | `backend/tests/` is empty; at minimum: BOCPD unit tests, cascade routing tests, time-travel truncation tests |
| Audit log frontend page (`/audit`) | Backend endpoint `GET /api/v1/audit` exists |
| Live alerts WebSocket (`/ws/alerts`) | Backend endpoint not yet built |
| Julius Baer investment model | `# TODO` in `ml/registry.py` |
| Ripple XRPL transaction model | `# TODO` in `ml/registry.py` |
| Voice biometric layer | Listed in onboarding doc; `ml/extractors/voice_authenticity.py` does not exist |
| Dark mode | Design tokens in `tailwind.config.ts`; not implemented |
| Mobile-responsive layout | Currently desktop-only |
| Postgres migration | SQLite is dev-only |
| CI/CD pipeline | No GitHub Actions |
| Production Docker profile | Current `docker-compose.yml` is dev-only |

---

## Priority Order for Remaining Hackathon Time

| Priority | Item | Effort | Impact |
|---|---|---|---|
| 🔴 P0 | Wire audit log into drift pipeline | 30 min | Closes BR6; makes time-travel story honest |
| 🔴 P0 | Decision bar on drift page | 2–3 h | Closes BR5; human-in-the-loop is now real |
| 🔴 P0 | At least one real T2 LLM call | 1–2 h | Makes cost-cascade metric honest |
| 🟠 P1 | Fix BOCPD changepoint on timeline | 1 h | Visual evidence the detection works |
| 🟠 P1 | Remove dead `if/pass` block in RFI | 15 min | Stops judges asking "what does this do?" |
| 🟠 P1 | Resolve SHAP claim (fix or reword) | 30 min–1 day | Prevents factual challenge in Q&A |
| 🟡 P2 | Move magic weights to config | 1 h | Code looks intentional, not hacked together |
| 🟡 P2 | Remove duplicate timeline endpoint | 15 min | Clean API surface |
| 🟢 P3 | Add basic BOCPD unit test | 1 h | Gives "we have tests" answer |
| 🟢 P3 | Qualify "real-time signals" in docs | 15 min | Pre-empts obvious Q&A challenge |
