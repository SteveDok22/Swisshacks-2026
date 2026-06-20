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
| 1 | Negative news spike | Reputational risk | ⚠️ PARTIAL | Lexicon classifier + confirmation lift; no live feed | Event Registry adapter (primary) + BOCPD on weekly event-count series; GDELT as fallback | **Wirecard** — adverse media, whistle-blower allegations, and accounting red flags accumulated in public signals 2 years before collapse |
| 2 | Cross-border transfer anomaly | Behavioural anomaly | ✅ WORKS | BOCPD + velocity on synthetic data | — | **Deutsche Bank mirror trades** — $10B moved Russia→UK via back-to-back exchange orders, evading cross-border transfer controls (2011–2015) |
| 3 | Multiple entities + sudden flows | Structuring / layering | ⚠️ PARTIAL | Contagion + causal; no named layering detector | GLEIF for real UBO graph to replace synthetic contagion graph | **Danske Estonia** — 15,000 non-resident shell-company customers, hidden UBO chains, €200B in suspicious cross-border flows |
| 4 | Jurisdiction / legal form change | Structural risk | 🔶 INDIRECT | `jurisdiction.py` is rule-pack selector, not change detector | ZEFIX / GLEIF diff vs. KYC baseline → `jurisdiction_change` signal | **Long Blockchain Corp** — Long Island Iced Tea rebranded to exploit crypto hype; name change triggered mandatory re-KYC across its banking relationships |
| 5 | New shareholders / UBOs | Ownership KYC drift | ⚠️ PARTIAL | PageRank over synthetic graph; no real UBO lookup | GLEIF ownership chain + OpenSanctions screening of each UBO | **1MDB** — beneficial ownership routed through multiple layers of Cayman/BVI shells; each UBO change further obscured the true principal |
| 6 | Large funding round / expansion | Scale risk | ⚠️ PARTIAL | `funding_event` template + causal; no live feed | Event Registry funding-event query + scale-jump ratio; GDELT fallback | **FTX** — $900M raise at $18B valuation; transaction volumes never matched claimed revenue; scale jump was the leading AML signal |
| 7 | Dormant company activates | Suspicious activation | ✅ WORKS | `drift/dormancy.py` explicit detector; wired into score + API; `dormancy_break` scenario in book; DormancyPanel in UI | — | **Azerbaijani Laundromat** — EU shell companies dormant for years, suddenly activated 2012–2014 to route $2.9B out of Azerbaijan |
| 8 | Legal entity name change | Re-KYC required | ❌ MISSING | Not implemented | ZEFIX + GLEIF diff against KYC baseline; `name_changed` signal; score floor at 60 | **Mossack Fonseca shelf cycling** — systematic renaming of shelf companies every 12–18 months to reset KYC review clocks |
| 9 | Domain switch / website change | Business activity change | ❌ MISSING | Not implemented | WHOIS registrant diff + Wayback (onboarding snapshot) + Firecrawl (current) + cosine distance | **N26** — rapid international expansion and domain/product proliferation outpaced AML monitoring; BaFin appointed a special monitor |
| 10 | Public business model pivot | Material business change | ❌ MISSING | Not implemented | Event Registry pivot-event cluster + Firecrawl + sentence-transformer cosine; GDELT fallback | **Centra Tech** — pivoted from debit-card fintech to ICO in 90 days; existing AML profile captured none of the new business model risk |

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

**3. Source adapters — carcasses exist in `backend/app/sources/`; `fetch`/`fetch_signals` are stubs**

Decision rule: **free/free-tier sources + Event Registry** (hackathon API key provided); other paid sources remain `SKIPPED`.
See [`docs/sources.md`](docs/sources.md) for full cost/access breakdown.

*Implement these (status: `PLANNED`):*
- [ ] **`sources/event_registry.py`** — structured news events, entity-aware queries (Cases 1, 6, 8, 10) · PAID — **hackathon API key provided; PRIMARY news source**
- [ ] **`sources/zefix.py`** — Swiss commercial register (Cases 4, 7, 8, 10) · FREEMIUM (free, but needs a free registered Basic-auth account — verified live 401 without creds; no officers/UBO in the API)
- [ ] **`sources/gleif.py`** — Global LEI Foundation (Cases 3, 4, 5, 8, 10) · FREE
- [ ] **`sources/opensanctions.py`** — OFAC / EU / UN sanctions + PEP screening (Cases 2, 5) · FREEMIUM
- [ ] **`sources/gdelt.py`** — GDELT 2.0 free news feed (Cases 1, 6, 8, 10) · FREE — **fallback** when Event Registry key absent
- [ ] **`sources/firecrawl.py`** — website-to-markdown scraping, current content (Cases 9, 10) · FREEMIUM
- [ ] **`sources/wayback.py`** — Internet Archive historical snapshot at onboarding date (Cases 9, 10) · FREE
- [ ] **`sources/whois.py`** — RDAP domain age + registrant change (Cases 8, 9) · FREE

- [ ] **`sources/event_registry.py`** — FREEMIUM, key-gated · `EVENT_REGISTRY_API_KEY` (Cases 1, 6, 8, 10) · Fully implemented; enriches GDELT with event-level de-duplication and structured sentiment when a key is present. Returns `[]` gracefully when no key is set so GDELT remains the always-on fallback.

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

**`FirecrawlAdapter`** (`sources/firecrawl.py`) — Current Website Content
- **What to fetch**: the live website content as clean markdown. The "after" reference for business-model drift.
- **`fetch(drift_id, name)`**
  - Get domain from `EntitySnapshotDB.extra["domain"]`
  - `POST https://api.firecrawl.dev/v1/scrape` with `{"url": f"https://{domain}", "formats": ["markdown"], "onlyMainContent": true}`
  - Parse `data.markdown` → trim to 10 kB
  - Return `EntitySnapshot(source="firecrawl", extra={"website_text": markdown[:10000], "scraped_at": now_iso})`
- **`fetch_signals`**: returns `[]` — signals are emitted by `drift/business_model.py`.
- **Auth**: `Authorization: Bearer {FIRECRAWL_API_KEY}` env var. If absent → return `EntitySnapshot` with empty `website_text` (graceful degradation; comparator skips if either text is empty).
- **Fallback**: if Firecrawl key is absent, attempt plain `httpx.get(domain)` + `BeautifulSoup` text extraction as a zero-cost fallback.

---

**5. Integration glue — wire adapters into the engine**

- [ ] **Refactor `public_intel.py` into aggregator** — `service.py` calls `generate_signals_for_customer()` which returns synthetic templates; replace with real adapter calls dispatched through `sources/registry.py`. This is the single step that makes every adapter actually run in the engine.
- [ ] **`drift/business_model.py`** — load Wayback text + Firecrawl text for a customer; embed both with `sentence-transformers/all-MiniLM-L6-v2` (14 MB, fully offline); `cosine_distance(wayback_embed, firecrawl_embed)` ≥ 0.35 → `PublicSignal(signal_type="business_model_change")`; store embeddings in `EntitySnapshotDB.extra` to skip re-embedding on re-scan.
- [ ] **`ml/extractors/drift.py`** — `DriftFeatureExtractor` with 20-dim feature vector; wire XGBoost to drift scoring (currently wired to case management only)
- [ ] **Train drift XGBoost model** — `ml/training.py` has no drift training path; feed synthetic book (8 scenarios × time windows ≈ 200 samples) through `DriftFeatureExtractor` → label → `XGBClassifier.fit()`

---

**6. Use case close-out tasks — one branch per use case**

Each task below flips one row in the Use Case Coverage table. Prerequisite: the relevant adapter(s) from section 3 must be implemented first.

> **UC 1 — Negative news spike** (⚠️ PARTIAL → ✅)
- [ ] Implement `EventRegistryAdapter.fetch_signals` news-volume + adverse-media modes (primary; see spec above); implement `GdeltAdapter.fetch_signals` volume mode as fallback
- [ ] Aggregator selects EventRegistry if `EVENT_REGISTRY_API_KEY` is set, else falls back to GDELT — single call site in `public_intel.py`
- [ ] Run BOCPD on weekly event-count series in `service.py:_analyze_customer`; surface `news_spike_month` in the analysis dict; feed into the confirmation-lift temporal window alongside internal BOCPD changepoint
- [ ] Add `news_spike` synthetic scenario to `simulator.py` — customer whose public_risk surges at month 9 via a news event-count spike; causal label `"risk"`

> **UC 3 — Multiple entities + sudden flows** (⚠️ PARTIAL → ✅)
- [ ] Implement `GleifAdapter.fetch` (ownership chain: parent LEI + direct children)
- [ ] In `DriftEngine.__init__`, if GLEIF is available, build `OwnershipGraph` from real LEI parent/child relationships instead of `build_demo_graph`
- [ ] Diff GLEIF `ownership_chain` vs KYC baseline using `diff_snapshots`; emit `ownership_change` signals

> **UC 4 — Jurisdiction / legal form change** (🔶 INDIRECT → ✅)
- [ ] Implement `ZefixAdapter.fetch` and `fetch_signals` (legal_form + jurisdiction diff path — see spec above)
- [ ] Implement `GleifAdapter.fetch` jurisdiction field (already in spec above)
- [ ] Extend `EntitySnapshotDB` with `legal_form: str | None` and `jurisdiction: str | None` columns so the diff has a persisted baseline to compare against
- [ ] A confirmed `jurisdiction_change` or `legal_form_change` signal floors the drift score at 50 in `service.py:_analyze_customer` (mandatory re-KYC trigger)

> **UC 5 — New shareholders / UBOs** (⚠️ PARTIAL → ✅)
- [ ] Implement `OpenSanctionsAdapter.fetch_signals` customer name screening path
- [ ] In the aggregator: fetch GLEIF `child_leis` → resolve each to entity name → screen through OpenSanctions; a UBO hit becomes `ownership_change` signal with UBO name in `detail`
- [ ] Surface UBO screening results (matched entity names + scores) in `DriftSubjectDetail` API response

> **UC 6 — Large funding round / expansion** (⚠️ PARTIAL → ✅)
- [ ] Implement `EventRegistryAdapter.fetch_signals` funding-events mode (primary); implement `GdeltAdapter.fetch_signals` funding mode as fallback
- [ ] Compute scale-jump ratio (`active_volume / baseline_volume`) in `causal.py`; if ratio ≥ 5× and a `funding_event` signal exists in the same window, raise `causal_p_risk` (corroborating that the volume jump is acquisition-driven rather than laundering)

> **UC 8 — Legal entity name change** (❌ MISSING → ✅)
- [ ] Implement `ZefixAdapter.fetch` + `fetch_signals` name-change diff path (see spec above)
- [ ] Implement `GleifAdapter.fetch` + `fetch_signals` name-change diff path (see spec above)
- [ ] Implement `WhoisAdapter.fetch` + `fetch_signals` domain registrant diff path (see spec above)
- [ ] Add `name_changed: bool` to the analysis dict in `service.py:_analyze_customer`; a confirmed name change floors the drift score at 60 regardless of other signals
- [ ] Add `name_cycling` synthetic scenario to `simulator.py` — customer whose legal name changes at month 6 (Mossack Fonseca pattern); ZEFIX + WHOIS signals fire; causal label `"risk"`
- [ ] Add `name` badge in `DriftRadar.tsx` (amber, mirrors `dormant` badge) when `is_name_changed` is true on the subject summary

> **UC 9 — Domain switch / website change** (❌ MISSING → ✅)
- [ ] Implement `WaybackAdapter.fetch` (historical snapshot path — see spec above)
- [ ] Implement `FirecrawlAdapter.fetch` (current content path — see spec above)
- [ ] Implement `WhoisAdapter.fetch_signals` domain registrant diff path
- [ ] Implement `drift/business_model.py` cosine comparator (Wayback text vs Firecrawl text via `all-MiniLM-L6-v2`)
- [ ] Add `is_business_model_change: bool` + `business_model_distance: float` to `DriftSubjectDetail` API response and surface in `TwoLayerPanel.tsx` alongside other public signals
- [ ] Add `domain_pivot` synthetic scenario to `simulator.py` — WHOIS registrant change at month 8 + high cosine distance; causal label `"risk"`

> **UC 10 — Public business model pivot** (❌ MISSING → ✅)
- [ ] Implement `EventRegistryAdapter.fetch_signals` pivot/rebrand mode (primary; see spec above); implement `GdeltAdapter.fetch_signals` pivot mode as fallback
- [ ] In the aggregator: if Event Registry reports a pivot-adjacent event cluster AND cosine distance ≥ 0.35, elevate signal severity to `"critical"` (two independent corroborating sources)
- [ ] Add `pivot` synthetic scenario to `simulator.py` — news pivot signals fire at month 9; website cosine distance fires; causal label `"risk"` with `funding_event` co-occurrence (Centra Tech pattern)

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
| Cost-Aware Cascade | `drift/cascade.py` | T0 rules → T1 LLR layer scoring → T2 LLM |
| Time-Travel Audit | `drift/timetravel.py` | No look-ahead bias on replay |
| Drift Engine | `drift/service.py` | All 7 layers, confirmation lift, LLM adjudication |
| Synthetic Book | `drift/simulator.py` | 8 scenarios with ground-truth labels |
| KYC Baseline Store | `db/kyc_baseline.py` | `EntitySnapshotDB` — onboarding + history snapshots |
| Source Adapter Layer | `sources/` | `RegistryAdapter` ABC + 7 planned + 3 SKIPPED carcasses |
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
| ZEFIX | 4, 7, 8, 10 | FREEMIUM¹ | 🔲 PLANNED |
| GLEIF | 3, 4, 5, 8, 10 | FREE | 🔲 PLANNED |
| OpenSanctions | 2, 5 | FREEMIUM | 🔲 PLANNED |
| Event Registry / NewsAPI.ai | 1, 6, 8, 10 | PAID (hackathon key) | 🔲 PLANNED — **primary news source** |
| GDELT | 1, 6, 8, 10 | FREE | 🔲 PLANNED — fallback when ER key absent |
| RDAP/WHOIS | 8, 9 | FREE | 🔲 PLANNED |
| Wayback Machine | 9, 10 | FREE | 🔲 PLANNED |
| Firecrawl | 9, 10 | FREEMIUM | 🔲 PLANNED |
| OpenCorporates | 3, 4, 5, 7 | PAID | ⛔ SKIPPED |
| EventRegistry / NewsAPI.ai | 1, 6, 8, 10 | FREEMIUM (key-gated) | ✅ IMPLEMENTED |
| Crunchbase | 6 | PAID | ⛔ SKIPPED |
| Internal transactions | 2, 3, 7 | — | ✅ Built |

¹ ZEFIX: free, but the REST API needs a free registered Basic-auth account (verified live — `401` without credentials). All cost tiers above were verified live against each API in June 2026.
