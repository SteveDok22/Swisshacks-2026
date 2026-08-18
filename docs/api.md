# API Reference

Base URL: `http://localhost:8000/api/v1` · Interactive docs: `http://localhost:8000/docs`

**28 endpoints across 10 routers.** (The OpenAPI schema reports 30 operations in
total — the two extras are the unversioned `GET /health` and `GET /` root.) No
authentication in the demo; CORS is open to `http://localhost:3000`.

---

## Drift Engine — `/drift`

| Method | Path | Purpose |
|---|---|---|
| GET | `/drift/subjects` | Risk-ranked list of all 20 subjects (15 synthetic + 5 live). `DriftSubjectSummary[]` — score, velocity band, risk level, `is_name_changed`, `mode`. |
| GET | `/drift/subjects/{drift_id}` | Full per-subject analysis — all 9 layers, causal verdict, stability, dormancy, timeline, public signals, UBO screening, website-drift. `DriftSubjectDetail`. |
| POST | `/drift/scan` | Run the cost-aware cascade over the whole book. `CascadeCostReport` — tier counts, cost vs LLM-on-all, real/cached T2 adjudication counts. |
| GET | `/drift/contagion` | Ownership graph + personalized-PageRank propagated risk from the sanctioned seed. `ContagionGraph`. |
| GET | `/drift/replay/{drift_id}` | Time-travel replay — score as-of any past month using only data available then (no look-ahead). `ReplayResult` with `lead_time_months`. |
| POST | `/drift/inject` | Red-team: synthesize a scenario on the fly (body: `scenario`, `name`). Volatile — lives one process. |
| POST | `/drift/rfi/{drift_id}` | Generate a Request-for-Information, questions ordered by value-of-information. `RFIResponse`. |

## Cases — `/cases`

| Method | Path | Purpose |
|---|---|---|
| GET | `/cases` | Filterable case queue (`?case_type=&status=&jurisdiction=&page=&page_size=`). `PaginatedResponse`. |
| GET | `/cases/{case_id}` | Case detail + full `context_data`. `CaseRead`. |
| POST | `/cases` | Create a case (body: `client_id`, `case_type`, `jurisdiction`, `context`). `201`. |
| PATCH | `/cases/{case_id}/status` | Update workflow status. |
| GET | `/cases/{case_id}/history` | This case's audit trail. `AuditEntryRead[]`. |

## Clients — `/clients`

| Method | Path | Purpose |
|---|---|---|
| GET | `/clients` | List all clients. `Client[]`. |
| GET | `/clients/{client_id}` | Client detail + KYC profile. |

## Decisions — `/decisions`

| Method | Path | Purpose |
|---|---|---|
| POST | `/decisions` | Record an officer decision (body: `case_id` **or** `drift_id`, `action`, `officer_id`, optional `rationale`). Appends to the audit log; overriding the AI requires a rationale. `201`. |
| GET | `/decisions/case/{case_id}` | Decisions for a case. |
| GET | `/decisions/subject/{drift_id}` | Decisions for a drift subject. |

## Audit — `/audit`

| Method | Path | Purpose |
|---|---|---|
| GET | `/audit` | Paginated, filterable audit log. `PaginatedResponse`. |

Filter params: `event_type`, `case_id`, `drift_id`, `actor_id`, `risk_level`,
`from_date`, `to_date`, `page`, `page_size`. The log is seeded with a realistic
~97-entry compliance trail (see [data-model.md](data-model.md)).

## Scoring — `/scoring`

| Method | Path | Purpose |
|---|---|---|
| POST | `/scoring/{case_id}` | Run ML scoring for a case. `ScoringResponse` — `risk_score`, `risk_level`, `confidence`, SHAP values. |
| GET | `/scoring/models` | List available ML models. |

## Explanations — `/explanations`

| Method | Path | Purpose |
|---|---|---|
| POST | `/explanations/{case_id}` | Generate a full case explanation. `CaseExplanation`. |
| GET | `/explanations/{case_id}/stream` | **SSE** streaming explanation — chunked tokens ("AI thinking" UX). |
| GET | `/explanations/{case_id}/anonymization` | Preview what is pseudonymized before it reaches the LLM. `AnonymizationPreview`. |

## Counterfactuals — `/counterfactuals`

| Method | Path | Purpose |
|---|---|---|
| POST | `/counterfactuals/{case_id}` | DiCE counterfactual scenarios ("what would flip this verdict"). `CounterfactualResponse`. |

## Jurisdictions — `/jurisdictions`

| Method | Path | Purpose |
|---|---|---|
| GET | `/jurisdictions` | List loaded rule packs (CH / EU / HK / AE). |
| GET | `/jurisdictions/{code}` | Rules for one jurisdiction. |
| POST | `/jurisdictions/compare/{case_id}` | Score a case under every jurisdiction at once. `dict[code, JurisdictionAdjustedScore]`. |

## Config — `/config`

| Method | Path | Purpose |
|---|---|---|
| GET | `/config` | Operating mode for the UI badge. `ConfigResponse`: `mode` (`synthetic`/`live`), `external_apis_enabled`, `llm_mode` (`mock`/`live`), `active_adapters[]`. |

---

## Response shapes

Schemas live in `backend/app/schemas/`. The richest is **`DriftSubjectDetail`**
(`schemas/drift.py`):

- `drift_score` (0–100), `risk_level`, `drift_velocity`, `velocity_band`, `reached_tier`, `recommended_action`, `mode`
- `layers[]` — per-layer LLR contributions; `timeline[]` — monthly trajectory + BOCPD changepoint marker
- `public_signals[]` — `signal_type`, `severity`, `headline`, `source`, `source_url`, `month` (news signals link to a direct article or carry no link — never a search page)
- `ubo_screening[]` — screened UBO, matched watchlist entity, score, `definitive`, `source_url` (UC5/UC8)
- `causal`, `stability`, `dormancy` — per-detector verdicts
- **UC9 website-drift**: `is_business_model_change`, `business_model_distance` (Wayback↔Firecrawl model2vec cosine; `≥ 0.35` flags a pivot), `onboarding_website_url`, `current_website_url`, `business_model_summary` (one-line LLM "what changed"). These default to neutral when no website text is available or the embedder is absent.

`CascadeCostReport` (`POST /drift/scan`) carries `tier_counts`, `total_cost`,
`llm_on_everything_cost`, `savings_pct`, and `real`/`cached` T2 call counts —
the live cost-efficiency evidence.

---

## Privacy

Case-explanation LLM calls pass through `services/anonymizer` first, so raw names
and exact amounts never reach Claude (pseudonyms + bucketed amounts). Drift T2
adjudication sends only structured, de-identified drift evidence — and only for
customers that actually reach the `T2_LLM` tier. With no Anthropic key (or
`ANTHROPIC_FORCE_MOCK=1`) the same path runs in deterministic mock mode. See
[architecture.md](architecture.md) and [drift-engine.md](drift-engine.md).
