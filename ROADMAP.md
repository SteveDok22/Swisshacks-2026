# Sentinel · Drift Engine — Task List

Challenge: [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md)

---

## Judging Criteria

| Criterion | Weight | Status |
|---|---|---|
| **AI Intelligence Quality** | 25% | ✅ Strong — 7 real algorithms, causal separation, suspicious stability |
| **Cost Efficiency** | 20% | ✅ Good — T2 LLM cascade works; per-workflow `tokens_used` + `model` tracked on every scan |
| **UX & Explainability** | 20% | ✅ Good — 7 visualisations solid; drift uses per-layer LLR contribution breakdown; signal cards include source citations; dormancy-break panel live |
| **Compliance & Safety** | 20% | ✅ Good — audit log wired; DecisionBar on drift; source citations surfaced |
| **Engineering & Architecture** | 15% | ✅ Good — modular engine, clean API, async, unit + BDD tests; no CI/CD |

---

## Use Case Coverage

| # | Use Case | Signal | Status | What exists | What's needed | Real-world example |
|---|---|---|---|---|---|---|
| 1 | Negative news spike | Reputational risk | ✅ WORKS | Event Registry (primary) / GDELT (fallback) selected at one call site; BOCPD on the weekly event-count series surfaces `news_spike_month` into the confirmation-lift window; `news_spike` scenario in the book | — | **Wirecard** — adverse media, whistle-blower allegations, and accounting red flags accumulated in public signals 2 years before collapse |
| 2 | Cross-border transfer anomaly | Behavioural anomaly | ✅ WORKS | BOCPD + velocity on synthetic data | — | **Deutsche Bank mirror trades** — $10B moved Russia→UK via back-to-back exchange orders, evading cross-border transfer controls (2011–2015) |
| 3 | Multiple entities + sudden flows | Structuring / layering | ✅ WORKS | Contagion + causal; real GLEIF LEI parent/child graph (`build_graph_from_snapshots`) with synthetic-demo fallback; `ownership_change` diff signals wired into the engine | — | **Danske Estonia** — 15,000 non-resident shell-company customers, hidden UBO chains, €200B in suspicious cross-border flows |
| 4 | Jurisdiction / legal form change | Structural risk | ✅ WORKS | ZEFIX/GLEIF diff vs. persisted KYC baseline; `jurisdiction_change`/`legal_form_change` floors drift score at 50 (re-KYC) | ZEFIX / GLEIF diff vs. KYC baseline → `jurisdiction_change` signal | **Long Blockchain Corp** — Long Island Iced Tea rebranded to exploit crypto hype; name change triggered mandatory re-KYC across its banking relationships |
| 5 | New shareholders / UBOs | Ownership KYC drift | ✅ WORKS | PageRank over synthetic graph **plus** real UBO screening: GLEIF ownership chain (direct-child LEIs → names) → OpenSanctions screening of each UBO; hits surfaced as `ownership_change` signals + `DriftSubjectDetail.ubo_screening` | — | **1MDB** — beneficial ownership routed through multiple layers of Cayman/BVI shells; each UBO change further obscured the true principal |
| 6 | Large funding round / expansion | Scale risk | ✅ | `funding_event` (ER/GDELT) + causal scale-jump corroboration | Event Registry funding-event query + scale-jump ratio; GDELT fallback | **FTX** — $900M raise at $18B valuation; transaction volumes never matched claimed revenue; scale jump was the leading AML signal |
| 7 | Dormant company activates | Suspicious activation | ✅ WORKS | `drift/dormancy.py` explicit detector; wired into score + API; `dormancy_break` scenario in book; DormancyPanel in UI | — | **Azerbaijani Laundromat** — EU shell companies dormant for years, suddenly activated 2012–2014 to route $2.9B out of Azerbaijan |
| 8 | Legal entity name change | Re-KYC required | ✅ DONE | `name_change` signal floors drift score at 60 (`service.py`); `name_cycling` scenario + ZEFIX/WHOIS synthetic signals; `is_name_changed` on summary API + `name` badge in `DriftRadar.tsx` | ZEFIX + GLEIF diff against KYC baseline; `name_changed` signal; score floor at 60 | **Mossack Fonseca shelf cycling** — systematic renaming of shelf companies every 12–18 months to reset KYC review clocks |
| 9 | Domain switch / website change | Business activity change | ✅ | `drift/business_model.py` comparator wired into `_analyze_customer` (folds a website pivot into the public layer); `is_business_model_change` + `business_model_distance` on `DriftSubjectDetail`, surfaced in `TwoLayerPanel.tsx`; `domain_pivot` synthetic scenario + demo-book customer | Deferred: source the two texts from Wayback/Firecrawl in live mode and persist embeddings in `EntitySnapshotDB.raw_data` | **N26** — rapid international expansion and domain/product proliferation outpaced AML monitoring; BaFin appointed a special monitor |
| 10 | Public business model pivot | Material business change | ✅ WORKS | Event Registry + GDELT pivot/rebrand `business_model_change` signals; `drift/business_model.py` cosine comparator; aggregator corroboration (`elevate_corroborated_pivots`) lifts a news-cluster + website-cosine pivot to critical; `pivot` synthetic scenario in `simulator.py` (Centra Tech pattern) | Live website-text wiring shares UC 9's pending `_analyze_customer` injection (load Wayback+Firecrawl texts) | **Centra Tech** — pivoted from debit-card fintech to ICO in 90 days; existing AML profile captured none of the new business model risk |

---

## ▶ Next Steps (current focus)

**Where we are:** all 8 free/freemium source adapters are implemented and unit-tested (GDELT is now built — the last adapter), **and the aggregator is wired**: `drift/service.py` calls `gather_public_signals_sync()` and `drift/public_intel.py` dispatches `fetch_signals()` to every usable adapter. Live adapter calls run only when `EXTERNAL_APIS_ENABLED` is set; the default-off path still uses the synthetic `generate_signals_for_customer()` templates. **The remaining work is per-use-case close-out** (business-model wiring, score floors, demo scenarios), not the core dispatch.

Do these in order:

1. ~~**Aggregator refactor — `drift/public_intel.py`** _(highest leverage; unblocks UC 1, 3, 4, 5, 6, 8, 9, 10 at once)_~~ ✅ **DONE** — `gather_public_signals()` dispatches to `sources/registry.py:usable_adapters()` in parallel; Event Registry is primary when `EVENT_REGISTRY_API_KEY` is set, GDELT is the free fallback. `service.py` calls it through `gather_public_signals_sync()` behind the `EXTERNAL_APIS_ENABLED` switch.

2. ~~**`drift/business_model.py` — Wayback↔Firecrawl cosine comparator** _(closes UC 9 comparator)_~~ ✅ **DONE** — embeds onboarding (Wayback) vs current (Firecrawl) website text with **model2vec static embeddings (pure NumPy, no torch; `sentence-transformers` swapped to keep the image lean)**; cosine distance ≥ 0.35 → `business_model_change`. Pure DB-free module + unit tests. **Remaining for UC 9 = aggregator wiring** (load the two texts per customer, persist embeddings) — folded into item 1.

3. **Score-flooring + scenarios** _(turns wired signals into table-flipping outcomes)_
   `jurisdiction_change`/`legal_form_change` floor score at 50; `name_changed` floors at 60 (UC 4, 8). Add `news_spike` (✅ done), `name_cycling`, `domain_pivot`, `pivot` synthetic scenarios to `simulator.py` so the demo exercises each path.

4. **Drift ML path** _(optional polish)_
   `ml/extractors/drift.py` (`DriftFeatureExtractor`, 20-dim) + drift training path in `ml/training.py`. Not on the UC critical path; defer if time-boxed.

> Detailed per-task breakdowns live under **P1 §5 (Integration glue)** and **P1 §6 (Use case close-out)** below.

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
- [x] **`db/kyc_baseline.py`** — `EntitySnapshotDB` SQLModel table + `store_snapshot`, `load_latest_snapshot`, `load_onboarding_snapshot`, `load_snapshot_history`, `load_all_baselines` CRUD helpers; registered in `session.py` so the table is auto-created on startup; 24 unit tests covering all helpers and seeding behaviour (PR #12)
- [x] **Seed KYC baselines** — `seed.py:_seed_kyc_baselines()` populates `entity_snapshots` from the synthetic drift book at startup; behavioral baseline (volume, counterparty/corridor risk, margin) computed from the pre-drift window so adapters have a numeric anchor to diff against (PR #12)
- [x] **`sources/base.py` + cost layer** — `RegistryAdapter` ABC + `EntitySnapshot` + canonical `PublicSignal` + `SnapshotDiff`/`diff_snapshots`; `sources/cost.py` (`SourceCost`/`AdapterStatus` enums, `CostMixin`); `sources/registry.py` free-vs-paid catalogue; carcass classes for all adapters. (PR #13)

**3. Source adapters — implemented adapters plus remaining carcasses in `backend/app/sources/`**

Decision rule: **free/free-tier sources + Event Registry** (hackathon API key provided); other paid sources remain `SKIPPED`.
See [`docs/sources.md`](docs/sources.md) for full cost/access breakdown.

*Implemented:*
- [x] **`sources/event_registry.py`** — structured news events, entity-aware queries (Cases 1, 6, 8, 10) · FREEMIUM — **hackathon API key; PRIMARY news source** · adverse-media, funding, name-change/pivot modes; returns `[]` gracefully when key absent
- [x] **`sources/zefix.py`** — Swiss commercial register (Cases 4, 7, 8, 10) · FREEMIUM · `fetch` + `fetch_signals` implemented against the live OpenAPI schema; Basic-auth from `ZEFIX_USERNAME`/`ZEFIX_PASSWORD`, graceful degradation without creds; unit tests in `tests/test_zefix.py`. Engine wiring tracked in UC4/UC8 close-out tasks below.
- [x] **`sources/gleif.py`** — Global LEI Foundation (Cases 3, 4, 5, 8, 10) · FREE · `fetch()` fully implemented (legal name, jurisdiction, LEI status, parent + child LEIs); `fetch_signals(baseline, current)` and the `ownership_change_signals()` helper diff the ownership chain via `diff_snapshots()` → `ownership_change` signals (no network in the diff path; `[]` when no snapshot pair is supplied)
- [x] **`sources/whois.py`** — RDAP domain age + registrant change (Cases 8, 9) · FREE · `fetch()` + `fetch_signals()` implemented against `rdap.org`; no key required; unit tests in `tests/test_whois.py`.

*All free / free-tier adapters implemented:*
- [x] **`sources/opensanctions.py`** — OFAC / EU / UN sanctions + PEP screening (Cases 2, 5) · FREEMIUM
- [x] **`sources/gdelt.py`** — GDELT 2.0 free news feed (Cases 1, 6, 8, 10) · FREE — **fallback** when Event Registry key absent · `fetch()→None`; `fetch_signals()` runs BOCPD over the raw article-count timeline (UC1) + classifies one `article_search` into funding (UC6) and pivot-cluster (UC10) signals via the `gdeltdoc` client; every query degrades to `[]` on error; unit tests in `tests/test_gdelt.py`
- [x] **`sources/firecrawl.py`** — website-to-markdown scraping, current content (Cases 9, 10) · FREEMIUM — key-optional (cloud `/scrape` → plain-HTTP strip → empty fallback)
- [x] **`sources/wayback.py`** — Internet Archive historical snapshot at onboarding date (Cases 9, 10) · FREE

*Paid — skipped (carcasses exist and document the decision):*
- [x] ~~**`sources/open_corporates.py`**~~ — PAID — SKIP (covered by GLEIF + ZEFIX)
- [x] ~~**`sources/crunchbase.py`**~~ — PAID — SKIP (funding news covered by Event Registry + GDELT)

**4. Adapter implementation specs — what each connector must fetch and return**

Each adapter has two methods to implement. `fetch()` returns a current `EntitySnapshot` (to be diffed against the KYC onboarding baseline from `db/kyc_baseline.py`). `fetch_signals()` returns `list[PublicSignal]` ready for the engine. Both currently raise `SourceUnavailableError` (stub). The `diff_snapshots()` helper in `sources/base.py` compares two snapshots field-by-field and returns a list of changed fields.

---

**`ZefixAdapter`** (`sources/zefix.py`) — Swiss Commercial Register
- **What to fetch**: company legal name, legal form (AG/GmbH/SA), registered canton (legal seat), status (ACTIVE / IN_LIQUIDATION / DELETED), last mutation date, `purpose` (Zweck) and SHAB publications. NOT available: officers / board members / UBOs (cantonal-register data only).
- **`fetch(drift_id, name)`**
  - `POST https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search` with `{"name": name, "maxEntries": 5, "languageKey": "en"}` → pick best name-match by Levenshtein distance
  - `GET /api/v1/company/uid/{uid}` → parse `legalName`, `legalForm`, `legalSeat`, `status`, `mutationDate`
  - Return `EntitySnapshot(source="zefix", name=legalName, legal_form=legalForm, jurisdiction=legalSeat, status=status, extra={"uid": uid, "mutation_date": mutationDate})`
- **`fetch_signals(drift_id, name, since_month)`**
  - Call `fetch()` → diff against `load_onboarding_snapshot(drift_id)` using `diff_snapshots()`
  - `name` changed → `PublicSignal(signal_type="name_change", severity="high", detail=f"{old} → {new}", source_url=record_url(uid))`
  - `legal_form` changed → `signal_type="legal_form_change"`, severity=`"medium"`
  - `jurisdiction` changed → `signal_type="jurisdiction_change"`, severity=`"high"`
  - `status` is `IN_LIQUIDATION` or `DELETED` → `signal_type="status_change"`, severity=`"critical"`
- **Auth**: **free registered Basic-auth account** required (verified live — `401 WWW-Authenticate: Basic` without credentials; request one from the Federal Office of Justice, zefix@bj.admin.ch). Add `User-Agent: Sentinel/1.0` header. Respect 429 with exponential backoff.
- **✅ IMPLEMENTED** (`sources/zefix.py`). The pseudocode above predates a live OpenAPI check — the shipped adapter follows the **real** contract: `search` body is `{"name", "activeOnly"}` (no `maxEntries`/`languageKey`) and returns `CompanyShort[]`; `GET /company/uid/{uid}` returns `CompanyFull[]`; `legalForm` is a nested `{de,fr,it,en}` map (we read `shortName`, preferring `de` → "AG"/"GmbH"); `status` ∈ {ACTIVE, BEING_CANCELLED, CANCELLED} mapped to the `dissolution_status` vocabulary. `jurisdiction` carries the Swiss **canton** (operative Case-4 seat; country is invariantly CH, kept in `raw_data`). `fetch_signals` diffs against a **caller-injected** `baseline` snapshot (no DB import in the adapter) and maps `diff_snapshots`' `*_changed` keys → noun-form `*_change` `PublicSignal`s. Credentials via `ZEFIX_USERNAME`/`ZEFIX_PASSWORD`; absent → graceful no-op.

---

**`GleifAdapter`** (`sources/gleif.py`) — Global Legal Entity Identifier
- **What to fetch**: global legal name, jurisdiction, LEI status, ultimate parent LEI, direct child LEIs (subsidiaries). This is the closest thing to a free global ownership tree.
- **`fetch(drift_id, name)`**
  - `GET https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]={name}&page[size]=5` → pick best match
  - `GET /lei-records/{lei}` → parse `entity.legalName`, `entity.jurisdiction`, `entity.status` (ISSUED/LAPSED/ANNULLED)
  - `GET /lei-records/{lei}/ultimate-parent` → store parent LEI
  - `GET /lei-records/{lei}/direct-children` → store list of child LEIs
  - Return `EntitySnapshot(source="gleif", name=legalName, jurisdiction=jurisdiction, status=status, extra={"lei": lei, "parent_lei": ..., "child_leis": [...]})`
- **`fetch_signals(drift_id, name, since_month)`**
  - Diff current vs onboarding snapshot:
  - `name` changed → `signal_type="name_change"`, severity=`"high"`
  - `jurisdiction` changed → `signal_type="jurisdiction_change"`, severity=`"high"`
  - `status` is ANNULLED or LAPSED → `signal_type="status_change"`, severity=`"critical"`
  - `parent_lei` changed → `signal_type="ownership_change"`, severity=`"high"`, detail=`f"Ultimate parent changed: {old_lei} → {new_lei}"`
  - New entries in `child_leis` vs baseline → `signal_type="ownership_change"`, severity=`"medium"`, detail=`"New subsidiary detected"`
- **Engine wiring**: in `DriftEngine.__init__`, if GLEIF is available, call `gleif.fetch()` per book customer and build a real `OwnershipGraph` from returned LEI parent/child relationships instead of the hardcoded `build_demo_graph`.
- **Auth**: none. Max 200 records/request. Respect 429.

---

**`OpenSanctionsAdapter`** (`sources/opensanctions.py`) — Sanctions & PEP Screening
- **What to fetch**: this is a screening source, not a registry. There is no entity snapshot to store — the result is always a list of signals.
- **`fetch(drift_id, name)`**: returns `None` always.
- **`fetch_signals(drift_id, name, since_month)`**
  - `GET https://api.opensanctions.org/search/default?q={name}&schema=Company&limit=5`
  - Score ≥ 0.85 → `PublicSignal(signal_type="sanctions", severity="critical", detail=f"Sanctions match: {caption} (score {score:.2f})", source_url=record_url(id))`
  - Score 0.70–0.85 → severity=`"high"`, detail notes it is a probable match requiring manual confirmation
  - **UBO chain screening**: accept optional `ubo_names: list[str]` kwarg; screen each UBO name separately; a UBO hit emits `signal_type="ownership_change"` with the UBO name in `detail`
- **Auth**: `Authorization: ApiKey {OPENSANCTIONS_API_KEY}` if set in env; falls back to unauthenticated free tier (tighter rate limits). No key required for non-commercial hackathon use.

---

**`EventRegistryAdapter`** (`sources/event_registry.py`) — Event Registry / NewsAPI.ai · PRIMARY NEWS SOURCE
- **What to fetch**: de-duplicated news events about a named entity, with per-event sentiment, relevance score, and article cluster. Preferred over GDELT because it is entity-aware (searches by concept/organisation URI, not raw text), de-duplicates syndicated coverage into single Events, and returns structured sentiment.
- **Auth**: `EVENT_REGISTRY_API_KEY` env var → sent as `"apiKey": key` in every POST body. Raise `SourceUnavailableError` if key absent (falls back to GDELT in aggregator).
- **`fetch(drift_id, name)`**: returns `None` — screening source, no canonical snapshot.
- **`fetch_signals(drift_id, name, since_month)`** — four query modes (all `POST /api/v1/event/getEvents`, JSON body):
  - **News volume / adverse media (UC 1)**: query `{"action": "getEvents", "keyword": name, "dateStart": since_date, "dateEnd": today, "lang": ["eng","deu","fra"], "sortBy": "date", "resultType": "timeline", "timelineStartDate": since_date, "timelineEndDate": today, "timelineInterval": "week"}` → weekly event-count series → BOCPD on the counts → if changepoint detected, also fetch `avgSentiment` for that window: negative sentiment → `PublicSignal(signal_type="news", severity="high", detail=f"News spike detected at {spike_date}, avg_sentiment={sentiment:.2f}")` ; neutral/positive → `severity="medium"`
  - **Adverse media events (UC 1 corroboration)**: same query but add `"categoryUri": "news/Business"` + filter events whose `avgSentiment < -0.3` → `signal_type="adverse_media"`, severity=`"high"`, `source_url` = event URL on eventregistry.org
  - **Funding events (UC 6)**: `{"keyword": f"{name} funding OR investment OR raised OR acquisition", "dateStart": since_date, ...}` → events within window → `signal_type="funding_event"`, severity=`"medium"`, detail = event title + article count
  - **Pivot / rebrand (UC 8, 10)**: `{"keyword": f"{name} rebranding OR renamed OR pivot OR \"business model\" OR \"new product\"", ...}` → cluster of ≥ 2 events within 90-day window → `signal_type="business_model_change"`, severity=`"high"`
- **Rate limit**: 2,500 req/day on hackathon tier. Cache `fetch_signals` results per `(drift_id, since_month)` tuple in `EntitySnapshotDB.extra["er_signals_cache"]` with a 6 h TTL to stay well within quota.

---

**`GdeltAdapter`** (`sources/gdelt.py`) — GDELT 2.0 Free News Feed · FALLBACK
- **When to use**: only if `EVENT_REGISTRY_API_KEY` is absent. The aggregator checks `EventRegistryAdapter.status` first; if unavailable, delegates to GDELT.
- **What to fetch**: global news article lists and weekly volume time-series, filterable by entity name and keyword. No canonical entity record — signals only.
- **`fetch(drift_id, name)`**: returns `None` always.
- **`fetch_signals(drift_id, name, since_month)`** — three separate query modes:
  - **News volume (UC 1)**: `GET https://api.gdeltproject.org/api/v2/doc/doc?query={name}&mode=timelinevol&format=json&TIMESPAN=12m` → parse weekly article counts → run BOCPD on the series → emit `PublicSignal(signal_type="news", severity=tone_to_severity(avg_tone))` when a changepoint is detected
  - **Funding events (UC 6)**: `GET ?query={name} funding OR investment OR raised&mode=artlist&format=json&MAXRECORDS=10` → articles within `since_month` window → emit `PublicSignal(signal_type="funding_event", severity="medium", source_url=article_url)`
  - **Pivot/rebrand (UC 10)**: `GET ?query={name} pivot OR rebranding OR "new product" OR "business model"&mode=artlist` → cluster of ≥ 3 articles within 60-day window → emit `PublicSignal(signal_type="business_model_change", severity="high")`
- **Auth**: none. **Must** send `User-Agent: Sentinel/1.0 (hackathon)` header or the API returns nothing. Respect 429 with 5 s backoff.
- **✅ IMPLEMENTED** (`sources/gdelt.py`). The shipped adapter uses the **`gdeltdoc`** client (synchronous, wrapped in `asyncio.to_thread`) instead of raw GETs: news-volume runs BOCPD over the `timelinevolraw` count series with severity derived from `timelinetone`; a single `article_search` covers funding (UC 6) and pivot (UC 10) via client-side title classification, with the pivot signal gated on a cluster of ≥ 3 articles inside a ~60-day window. `gdeltdoc` sets its own `User-Agent`; each query independently degrades to `[]` on any error. A `GdeltDoc` client is injectable for tests. The aggregator-selection / explicit-`User-Agent` / 429-backoff notes above predate the `gdeltdoc` switch.

---

**`WhoisAdapter`** (`sources/whois.py`) — RDAP Domain Registration
- **What to fetch**: domain registration date, last-changed date, registrar, registrant organisation name. Used to detect a silent domain handover or a domain registered long after the company's claimed founding date.
- **`fetch(drift_id, name)`**
  - Get domain from `EntitySnapshotDB.extra["domain"]`; if absent, try `{name_slug}.com` heuristic
  - `GET https://rdap.org/domain/{domain}` → parse registration date, last-changed date, registrar, registrant org
  - Return `EntitySnapshot(source="whois", extra={"domain": domain, "registered_at": registration_date, "last_changed": last_changed_date, "registrar": registrar_name, "registrant_org": org})`
- **`fetch_signals(drift_id, name, since_month)`**
  - Diff current vs onboarding snapshot:
  - `registrant_org` changed → `signal_type="domain_change"`, severity=`"high"`, detail=`f"Registrant changed: {old} → {new}"`
  - Domain age < 180 days but company claims > 2 years established → `signal_type="domain_change"`, severity=`"medium"`, detail=`"Domain registered recently vs claimed company age"`
- **Rate limit**: rdap.org allows ~10 req / 10 s. For higher volume, read IANA bootstrap `https://data.iana.org/rdap/dns.json` and query TLD-specific servers directly.
- **✅ IMPLEMENTED** (`sources/whois.py`). The shipped adapter uses the free RDAP path (`rdap.org`, no key): `fetch(domain=...)` normalizes registration date, last-changed date, registrar, registrant org, status, and RDAP handle into `EntitySnapshot.raw_data`; absent domain falls back to `url`/`website` kwargs and then `{name_slug}.com`. `fetch_signals` diffs a caller-injected same-source baseline for registrant-org changes and emits young-domain signals only when the caller provides a company-age hint (`claimed_company_age_days` or `company_founded_at`) showing the company claims to be older than two years. Unit tests in `tests/test_whois.py`.

---

**`WaybackAdapter`** (`sources/wayback.py`) — Internet Archive Historical Snapshots
- **What to fetch**: the website content as it existed at KYC onboarding. This is the "before" reference for business-model drift; it is never diffed alone — always paired with Firecrawl's current snapshot by `drift/business_model.py`.
- **`fetch(drift_id, name)`**
  - Get onboarding date from `EntitySnapshotDB`; format as `yyyymmdd`
  - `GET https://archive.org/wayback/available?url={domain}&timestamp={yyyymmdd}` → get nearest snapshot URL
  - Fetch snapshot page from `https://web.archive.org/web/{timestamp}/{domain}` → strip HTML → keep plain text (max 10 kB)
  - Return `EntitySnapshot(source="wayback", extra={"snapshot_url": url, "snapshot_date": date, "website_text": text[:10000]})`
- **`fetch_signals`**: returns `[]` — Wayback is a reference-only source; signals are emitted by `drift/business_model.py` after cosine comparison with Firecrawl.
- **Storage**: persist `website_text` in `EntitySnapshotDB.extra` after first fetch so it is not re-fetched on every scan. Add polite 1 s delay between requests.

---

**`FirecrawlAdapter`** (`sources/firecrawl.py`) — Current Website Content ✅ IMPLEMENTED
- **What to fetch**: the live website content as clean markdown. The "after" reference for business-model drift.
- **`fetch(drift_id, name, *, domain)`** — the caller injects `domain` (read from `EntitySnapshotDB.extra["domain"]`); the adapter never touches the DB, preserving the `sources` dependency rule.
  - Normalise `domain` to a bare host (strip scheme/path/case) → `url = f"https://{host}"`.
  - **Tier 1 (key present)**: `POST https://api.firecrawl.dev/v1/scrape` with `{"url": url, "formats": ["markdown"], "onlyMainContent": true}`; parse `data.markdown`.
  - **Tier 2 (no key, or Tier 1 failed)**: plain `httpx.GET(url)` + a stdlib `html.parser` HTML-to-text strip (drops `script`/`style`/`head`) — zero cost, **no `BeautifulSoup` dependency added**.
  - **Tier 3**: page unreachable (or a literal internal/loopback host, blocked by a lightweight SSRF guard) → empty `website_text` (comparator skips when either side is empty).
  - Store the result in `raw_data` (`EntitySnapshot` has no `extra` field — that is the ORM model's): `raw_data={"domain", "url", "website_text": text[:10000], "scraped_at": now_iso, "scrape_method"}`.
  - Returns `None` **only** when no `domain` is supplied.
- **`fetch_signals`**: returns `[]` — signals are emitted by `drift/business_model.py`.
- **Auth**: `Authorization: Bearer {FIRECRAWL_API_KEY}` (config `firecrawl_api_key`). The key is **optional** thanks to the Tier-2/3 fallback ladder above.

---

**5. Integration glue — wire adapters into the engine**

- [x] **Refactor `public_intel.py` into aggregator** — `gather_public_signals()` (async) dispatches `fetch_signals()` to all `usable_adapters()` in parallel via `asyncio.gather`; `gather_public_signals_sync()` bridges sync `DriftEngine._analyze_customer()` via a thread-isolated `asyncio.run()`; `service.py` now calls real adapters instead of synthetic templates (gated by the `EXTERNAL_APIS_ENABLED` master switch — synthetic fallback when offline). Engine tests patched via `conftest.py` autouse fixture to keep tests fast.
- [x] **`drift/business_model.py`** — loads Wayback text + Firecrawl text for a customer and emits `PublicSignal(signal_type="business_model_change")` when `cosine_distance(wayback_embed, firecrawl_embed) ≥ 0.35` (severity `clip(0.20 + 1.30 × distance, 0, 0.95)`). Embeds with **model2vec `minishlab/potion-base-8M`** — a static MiniLM-class distillation running on **pure NumPy (no torch)**, ~30 MB, fully offline — instead of `sentence-transformers` (torch ~2 GB). Optional `embeddings` extra; absent → degrades to no signal. Pluggable `Embedder` protocol; re-embedding cache keyed by SHA-256 fingerprint (caller persists vectors in `EntitySnapshotDB.raw_data`). DB-free pure module; unit tests in `tests/test_business_model.py`. **Wired into `_analyze_customer`** (folds a website pivot into the public layer; exposed via `is_business_model_change` / `business_model_distance` on `DriftSubjectDetail`). Remaining follow-up: source the two texts from Wayback/Firecrawl in live mode and persist embeddings in `EntitySnapshotDB.raw_data` to skip re-embedding.
- [x] **`ml/extractors/drift.py`** — `DriftFeatureExtractor` with 20-dim feature vector covering all engine layers (velocity, BOCPD, causal signature, suspicious stability, dormancy break); `DriftEngine._analyze_customer()` blends ML probability into the heuristic score (60% heuristic + 40% XGBoost) when a trained model is present; graceful no-op when model absent; unit tests in `tests/test_drift_ml.py`.
- [x] **Train drift XGBoost model** — `ml/training.py` has a `train_drift_model()` path; `generate_drift_training_data()` generates 8 scenarios × N samples via standalone analysis (no live DriftEngine); labels risk vs benign by scenario; registered in `ml/registry.py` as `CaseType.KYC_DRIFT`; CLI: `python -m app.ml.training train-drift`.

---

**6. Use case close-out tasks — one branch per use case**

Each task below flips one row in the Use Case Coverage table. Prerequisite: the relevant adapter(s) from section 3 must be implemented first.

> **UC 1 — Negative news spike** (⚠️ PARTIAL → ✅ DONE)
- [x] Implement `EventRegistryAdapter.fetch_signals` — adverse-media / news-spike modes (primary; hackathon key)
- [x] Implement `GdeltAdapter.fetch_signals` — volume + adverse-media modes (free fallback when key absent)
- [x] Aggregator selects EventRegistry if `EVENT_REGISTRY_API_KEY` is set, else falls back to GDELT — single call site (`_select_news_source` in `public_intel.py`, applied once in `gather_public_signals`; the non-selected news adapter is dropped so the two never double-count)
- [x] Run BOCPD on weekly event-count series in `service.py:compute_drift_analysis` (`detect_news_spike_month`); surface `news_spike_month` in the analysis dict; feed it into the confirmation-lift temporal window alongside the internal BOCPD changepoint (a sustained-elevation guard keeps the stable control silent)
- [x] Add `news_spike` synthetic scenario to `simulator.py` — customer whose public_risk surges via a sustained adverse-media spike from the drift onset (default month 9), with co-occurring internal volume drift + margin collapse; causal label `"risk"`; seeded as "Wirecard Holdings AG" in the demo book

> **UC 3 — Multiple entities + sudden flows** (⚠️ PARTIAL → ✅)
- [x] Implement `GleifAdapter.fetch` (ownership chain: parent LEI + direct children)
- [x] In `DriftEngine.__init__`, if GLEIF is available, build `OwnershipGraph` from real LEI parent/child relationships instead of `build_demo_graph` (`DriftEngine._build_ownership_graph` → `contagion.build_graph_from_snapshots`; degrades to `build_demo_graph` when GLEIF is offline/unreachable or resolves no ownership links)
- [x] Diff GLEIF `ownership_chain` vs KYC baseline using `diff_snapshots`; emit `ownership_change` signals (`gleif.ownership_change_signals` + `GleifAdapter.fetch_signals`, layered into the engine via `DriftEngine._gleif_ownership_signals`). Follow-up: persist GLEIF-source onboarding baselines so the live demo diff fires (the seed currently writes `internal`-source baselines, which the same-source contract excludes); seed a flagged entity into the real graph so contagion propagates over live LEIs.

> **UC 4 — Jurisdiction / legal form change** (🔶 INDIRECT → ✅)
- [x] Implement `ZefixAdapter.fetch` and `fetch_signals` (legal_form + jurisdiction diff path — see spec above)
- [x] Implement `GleifAdapter.fetch` jurisdiction field (already in spec above)
- [x] Extend `EntitySnapshotDB` with `legal_form: str | None` and `jurisdiction: str | None` columns so the diff has a persisted baseline to compare against (columns present + seeded by `_seed_kyc_baselines`; round-trip + seed coverage in `tests/test_kyc_baseline.py`)
- [x] A confirmed `jurisdiction_change` or `legal_form_change` signal floors the drift score at 50 in `service.py:_analyze_customer` (mandatory re-KYC trigger) — `requires_re_kyc_floor` / `RE_KYC_SCORE_FLOOR`; tests in `tests/test_score_boundaries.py`, adapter contract in `tests/test_zefix.py`

> **UC 5 — New shareholders / UBOs** (⚠️ PARTIAL → ✅) — **DONE** (PR #36)
- [x] Implement `OpenSanctionsAdapter.fetch_signals` customer name screening path — name screening (score ≥ 0.85 → `sanctions` critical; 0.70–0.85 → high/probable) + `ubo_names` kwarg screening each UBO into `ownership_change` signals carrying structured `meta` (screened name, matched entity, score)
- [x] In the aggregator: fetch GLEIF `child_leis` → resolve each to entity name → screen through OpenSanctions; a UBO hit becomes `ownership_change` signal with the UBO name — `drift/public_intel.py` resolves the GLEIF ownership chain (direct-child LEIs → legal names, capped) and passes them as `ubo_names`; GLEIF located by `source_name` among `usable_adapters()` so the step is inert offline / in mocked tests
- [x] Surface UBO screening results (matched entity names + scores) in `DriftSubjectDetail` API response — new `UboScreeningOut` schema + `DriftSubjectDetail.ubo_screening`, built from the screened-UBO signals' `meta` (no headline parsing)

> **UC 6 — Large funding round / expansion** (⚠️ PARTIAL → ✅)
- [x] Implement `EventRegistryAdapter.fetch_signals` — funding-events mode (primary)
- [x] Implement `GdeltAdapter.fetch_signals` — funding mode (free fallback)
- [x] Compute scale-jump ratio (`active_volume / baseline_volume`) in `causal.py`; if ratio ≥ 5× and a `funding_event` signal exists in the same window, raise `causal_p_risk` (corroborating that the volume jump is acquisition-driven rather than laundering) — `CausalSignature.scale_jump_ratio` + `classify_causal(funding_corroborated=…)` add a fixed LLR boost; `causal_assessment` aligns funding-event months to the recent window; wired in `service.py:compute_drift_analysis`

> **UC 8 — Legal entity name change** (❌ MISSING → ✅)
- [x] Implement `ZefixAdapter.fetch` + `fetch_signals` name-change diff path (see spec above)
- [x] Implement `GleifAdapter.fetch` name-change diff path — `fetch()` done; `fetch_signals()` returns `[]` by design; service layer calls `diff_snapshots()` to emit signals
- [x] Implement `WhoisAdapter.fetch` + `fetch_signals` domain registrant diff path (see spec above)
- [x] Add `name_changed: bool` to the analysis dict in `service.py:_analyze_customer`; a confirmed name change floors the drift score at 60 regardless of other signals
- [x] Add `name_cycling` synthetic scenario to `simulator.py` — customer whose legal name changes at month 6 (Mossack Fonseca pattern); ZEFIX + WHOIS signals fire; causal label `"risk"`
- [x] Add `name` badge in `DriftRadar.tsx` (amber, mirrors `dormant` badge) when `is_name_changed` is true on the subject summary

> **UC 9 — Domain switch / website change** (❌ MISSING → ✅)
- [x] Implement `WaybackAdapter.fetch` (historical snapshot path — see spec above)
- [x] Implement `FirecrawlAdapter.fetch` (current content path — key-optional: cloud `/scrape` → plain-HTTP HTML strip → empty snapshot; `fetch_signals` is a no-op by design)
- [x] Implement `WhoisAdapter.fetch_signals` domain registrant diff path
- [x] Implement `drift/business_model.py` cosine comparator (Wayback text vs Firecrawl text; **model2vec static embeddings, pure NumPy, no torch** — see §5)
- [x] Add `is_business_model_change: bool` + `business_model_distance: float` to `DriftSubjectDetail` API response and surface in `TwoLayerPanel.tsx` alongside other public signals
- [x] Add `domain_pivot` synthetic scenario to `simulator.py` — WHOIS registrant change at month 8 + high cosine distance; causal label `"risk"`

> **UC 10 — Public business model pivot** (❌ MISSING → ✅)
- [x] Implement `EventRegistryAdapter.fetch_signals` — pivot/rebrand mode (primary)
- [x] Implement `GdeltAdapter.fetch_signals` — pivot mode (free fallback)
- [x] In the aggregator: if Event Registry reports a pivot-adjacent event cluster AND cosine distance ≥ 0.35, elevate signal severity to `"critical"` (two independent corroborating sources) — `public_intel.elevate_corroborated_pivots`, applied in `gather_public_signals` (live) and the synthetic generator (offline). The website-derived `business_model_change` signal only exists when distance ≥ 0.35, so its presence *is* that condition; "critical" = the top 0.90–1.00 severity band
- [x] Add `pivot` synthetic scenario to `simulator.py` — news pivot signals fire at month 9; website cosine distance fires; causal label `"risk"` with `funding_event` co-occurrence (Centra Tech pattern). Transaction signature is risk-shaped (volume up, margin collapse); public signals emitted by `generate_signals_for_customer`

---

### P2 — Engineering cleanups

- [x] Move 6 magic-number layer weights from `service.py` to named constants in `core/config.py`
- [x] Add single-worker warning to the global `_engine` singleton (unsafe under multi-process)
- [x] Remove duplicate timeline endpoint — `GET /drift/subjects/{drift_id}` already returns the timeline
- [x] Fix `db_store.py` — `len(list(...all()))` loads all case IDs for count; replaced with `COUNT(*)` query via `func.count()`
- [x] `list_subjects()` recomputes all subjects on every request — added 30 s TTL cache on `DriftEngine`
- [x] Qualify "real-time signals" language in README and pitch — signals are simulated for MVP; architecture is slot-swap ready
- [x] `DormancyPanel.tsx` — dormancy-break panel live in Drift workspace; `DormancyVerdict` TS types synced with backend `DormancyOut` (PR #21)
- [x] Token usage per workflow — `tokens_used` + `model` on `CascadeCostReport`; populated from Anthropic API response metadata; `real_t2_llm_calls` correctly excludes cache hits (PR #20)

---

### P3 — Nice to have

- [x] **`time_travel.feature`** BDD test — replay uses only data available at as-of date; lead time is positive
- [x] **`test_hypothesis_h1.py`** — BOCPD lead time ≥ 2 months on drifting scenarios; 0 false positives on stable scenario
- [x] **`test_hypothesis_h2.py`** — velocity alert fires earlier than absolute-threshold alert at equal false-positive rate
- [x] **`test_hypothesis_h3.py`** — 2-hop contagion customers elevated; 3+ hop not elevated
- [x] **`test_hypothesis_h4.py`** — cascade cost < 10% of LLM-on-everything; high-risk recall unchanged

---

## What Is Already Built (reference)

| Component | File | Notes |
|---|---|---|
| BOCPD | `drift/bocpd.py` | Adams & MacKay 2007, Normal-Inverse-Gamma priors |
| Drift Velocity | `drift/velocity.py` | Closed-form Gaussian KL, smoothed first-differencing |
| Ownership Contagion | `drift/contagion.py` | NetworkX personalized PageRank |
| Causal Drift | `drift/causal.py` | Neyman-Pearson likelihood-ratio |
| Suspicious Stability | `drift/stability.py` | CV × environmental movement |
| Dormancy Break | `drift/dormancy.py` | Near-zero baseline × activation burst |
| Business-Model Drift | `drift/business_model.py` | Wayback↔Firecrawl website cosine distance ≥ 0.35; model2vec static embeddings (pure NumPy, no torch); DB-free comparator |
| Cost-Aware Cascade | `drift/cascade.py` | T0 rules → T1 LLR layer scoring → T2 LLM |
| Time-Travel Audit | `drift/timetravel.py` | No look-ahead bias on replay |
| Drift Engine | `drift/service.py` | All 7 layers, confirmation lift, LLM adjudication |
| Synthetic Book | `drift/simulator.py` | 8 scenarios with ground-truth labels |
| KYC Baseline Store | `db/kyc_baseline.py` | `EntitySnapshotDB` — onboarding + history snapshots |
| Source Adapter Layer | `sources/` | `RegistryAdapter` ABC; all 8 free/freemium adapters implemented (GLEIF, ZEFIX, EventRegistry, OpenSanctions, GDELT, Wayback, WHOIS/RDAP, Firecrawl); 2 SKIPPED (paid). **Wired into the engine via `drift/public_intel.py`, gated by `EXTERNAL_APIS_ENABLED`.** |
| REST API | `api/v1/` | 27 endpoints, all functional |
| Frontend | `src/app/drift/`, `src/app/audit/` | 8 drift panels + audit log page + dormancy-break panel |
| XGBoost + SHAP | `ml/base.py` | Wired to case management only; drift uses per-layer LLR breakdown |
| Audit service | `services/audit.py` | Append-only, queried by subject and event type |
| Claude AI | `services/anthropic_client.py` | T2 adjudication + case explanations; mock mode works without key |
| Jurisdiction packs | `services/jurisdiction.py` | CH / EU / HK / AE |

---

## Source → Use Case Matrix

| Source | Cases | Cost | Status |
|---|---|---|---|
| ZEFIX | 4, 7, 8, 10 | FREEMIUM¹ | ✅ IMPLEMENTED (engine wiring pending) |
| GLEIF | 3, 4, 5, 8, 10 | FREE | ✅ IMPLEMENTED — `fetch()` live; ownership graph via `build_graph_from_snapshots`; `ownership_change` signals via `diff_snapshots()` |
| OpenSanctions | 2, 5 | FREEMIUM | ✅ IMPLEMENTED — `fetch_signals` live; key optional (non-commercial free tier) |
| Event Registry / NewsAPI.ai | 1, 6, 8, 10 | FREEMIUM (hackathon key) | ✅ IMPLEMENTED — **primary news source** |
| GDELT | 1, 6, 8, 10 | FREE | ✅ IMPLEMENTED — `fetch_signals` live (BOCPD volume + funding/pivot title classification); free fallback when ER key absent |
| RDAP/WHOIS | 8, 9 | FREE | ✅ IMPLEMENTED — `fetch()` + `fetch_signals()` live; no key required |
| Wayback Machine | 9, 10 | FREE | ✅ IMPLEMENTED — `fetch()` live; `fetch_signals()` returns `[]` by design |
| Firecrawl | 9, 10 | FREEMIUM | ✅ IMPLEMENTED — key-optional (cloud → plain-HTTP fallback); comparator built (`drift/business_model.py`); aggregator wiring pending |
| OpenCorporates | 3, 4, 5, 7 | PAID | ⛔ SKIPPED |
| Crunchbase | 6 | PAID | ⛔ SKIPPED |
| Internal transactions | 2, 3, 7 | — | ✅ Built |

¹ ZEFIX: free, but the REST API needs a free registered Basic-auth account (verified live — `401` without credentials). All cost tiers above were verified live against each API in June 2026.

---

## Demo Data Refresh & Two-Mode (synthetic / real) — PLAN

> Added after a full project review. Goal: one cohesive, demo-ready KYC-drift
> book that fires **all 10 AMINA use cases offline**, plus a clean
> `EXTERNAL_APIS_ENABLED` flip to a **genuinely live** demo. Dev/tests stay
> offline by default. Status below = **planned** unless checked.

### Decisions (locked)
- **All-in on drift.** Retire the old social-engineering / XRPL case-review dataset (`services/mock_data.py`); drift is the whole demo. Keep the code dormant (don't delete) to avoid breaking imports/tests.
- **Fictional-but-evocative names**, each with a one-line backstory + real-world analogue cited in docs (not as the entity name).
- **Real mode = every source except ZEFIX** (no account). Keys present in `.env.shared` / `.env`: OpenSanctions, Event Registry, Firecrawl, WHOISJSON, Anthropic. Keyless: GLEIF, GDELT, Wayback, WHOIS/RDAP.
- **Provenance is first-class:** every signal carries a *real, clickable* source link in both modes (synthetic → source's search page for the entity; live → the actual matched record).

### The new cast — 15 entities (12 flagged + 3 stable controls)

| # | Entity (fictional) | UC(s) | Scenario | Backstory / analogue |
|---|---|---|---|---|
| 1 | Helvetia Pharma Holding AG (Zug) | UC1 | `news_spike` | Adverse media accrues for months pre-collapse (Wirecard) |
| 2 | Léman FX Trading SA (Geneva) | UC2 | `corridor_shift` + new corridor signal | Corridors drift CH/DE→RU/AE; money-mule (DB mirror trades) |
| 3 | Alpine Logistics Group AG + 2 shell owners | UC3 | `combined` + contagion | Linked shells, sudden layering flows (Danske Estonia) |
| 4 | Glarnisch Holding AG (ex–Pilatus Commodity Reg.) | UC4 | `name_cycling` | Renamed to reset KYC clock (Mossack shelf-cycling) |
| 5 | HelvetiaX (ex–Helvetia Advisory AG) | UC5 | `domain_pivot` | Website flips advisory→crypto exchange |
| 6 | Lattice Labs AG (Zurich) | UC6 | `pivot` *(instantiate unused scenario)* | SaaS→ICO in 90 days (Centra Tech) |
| 7 | Rhône Capital GmbH → Ltd (BVI) | UC7 | `jurisdiction_shift` *(NEW scenario)* | GmbH→offshore legal-form/jurisdiction move |
| 8 | Bernina Wealth Partners AG | UC8 | `ownership_shift` *(new UBO)* | New beneficial owner who hits a watchlist (1MDB) |
| 9 | Nimbus Mobility AG | UC9 | `benign_expansion` vs scale flag | Large funding round / geo expansion (FTX scale-vs-revenue) |
| 10 | Säntis Import-Export AG (ex–Dormant Holdings) | UC10 | `dormancy_break` | Dormant shell reactivates (Azerbaijani Laundromat) |
| 11 | Castor Trade Finance AG ⭐ | UC3+UC8+UC1 | `combined` + UBO hit + adverse media | **Flagship combo** — structuring + sanctioned new UBO + news; contagion centerpiece, routes to T2 Claude |
| 12 | Engadin Capital SA | behavioral combo | `suspicious_stability` | Slow-walker: too smooth while environment moves |
| 13 | Zürisee Renewables AG | control | `benign_expansion` | Legit growth despite adverse news — causal layer demotes it |
| 14 | Toggenburg Family Office | control | `stable` | Clean baseline |
| 15 | Vaud AgriTech SA | control | `stable` | Clean baseline |

### Phases

- [ ] **A — Retire old dataset.** Stop seeding `mock_data.py` clients/cases; remove `/` case-review workspace from nav; make drift the home page. Keep code dormant.
- [ ] **B — Rebuild the drift book** (`drift/simulator.py`, `db/seed.py`): 15-entity cast w/ backstories; **instantiate `pivot`** (UC6); **add `jurisdiction_shift` scenario** (UC7, emits `jurisdiction_change`+`legal_form_change`, exercises the existing re-KYC floor=50); **add UBO scenario** (UC8, ownership_change with a name that hits OpenSanctions live + deterministic synthetic hit); wire flagship combo (#11) into the contagion graph.
- [ ] **C — Close detector/signal gaps.** New `corridor_alert` public signal so UC2 is self-contained; tune dormancy baseline to a realistic non-zero floor; keep H1–H4 hypothesis tests green after re-seed.
- [ ] **D — Real provenance links (both modes).** Replace `example.com/demo-sources/...` with per-source deep-link builders (OpenSanctions `search?q=`, GLEIF LEI page, GDELT/Event Registry query/article, Wayback snapshot, RDAP domain). Universal clickable source chips on every signal card + UBO hit.
- [ ] **E — Two-mode UX.** Header indicator SYNTHETIC vs LIVE (driven by `external_apis_enabled`), replacing the static "Live" dot; per-signal real-source badge in live mode; confirm `.env` keeps dev offline.
- [ ] **F — Real-mode demo anchors (all sources except ZEFIX).** Curate real LEIs (GLEIF), real domains (Wayback/Firecrawl/WHOIS), and ≥1 real sanctioned name as a UBO so the live demo returns a genuine OpenSanctions hit w/ real deep-link. Map each UC → live source; document UC4/UC7 demoed via GLEIF legalName/jurisdiction/legalForm diff + rename news (no ZEFIX).
- [ ] **G — Frontend demo polish.** Wayback↔Firecrawl side-by-side text diff for UC5/6; scenario label on the timeline; source-link chips on signal cards.
- [ ] **H — Docs + tests.** Update this UC table, `sources.md`, README; refresh seed; run `uv run pytest` + ruff/mypy via Docker.

### Open confirmations
- Entity **names** above are a proposal — adjust freely.
- For the live OpenSanctions hit: use a well-known OFAC-listed name as a fictional customer's **UBO** purely so the live screen returns a real match (confirm).
