# Sentinel — Source Adapters (`backend/app/sources/`)

> The Public Intelligence layer (Layer 2) draws on external sources and turns
> each observed change into a `PublicSignal` the drift engine fuses with internal
> bank data. This document is the catalogue: **what each source provides, whether
> it is free and usable right now, and which ones we deliberately skip.**
>
> Companion to [`source-integration-architecture.md`](source-integration-architecture.md)
> (the pipeline design) and [`drift-engine.md`](drift-engine.md).

---

## Status: partial implementation

Seven adapters are fully implemented (real HTTP calls):
- **WHOIS / RDAP** — free, no key required; returns RDAP domain metadata and domain-change signals from injected baselines (PR #29)
- **GLEIF** — free, no key required (PR #25)
- **ZEFIX** — FREEMIUM, free Basic-auth account; degrades gracefully (`None`/`[]`) when credentials absent (PR #23)
- **Event Registry** — FREEMIUM, key-gated; returns `[]` when key absent (PR #24)
- **OpenSanctions** — FREEMIUM, key optional; unauthenticated non-commercial free tier works without a key (PR #27)
- **Wayback Machine** — free, no key required; `fetch_signals()` returns `[]` by design (signals via `drift/business_model.py`) (PR #26)
- **Firecrawl** — FREEMIUM, key optional; cloud `/scrape` with key, else a zero-cost plain-HTTP + HTML-strip fallback (this PR)

Remaining carcasses — no real network I/O yet:

- `base.py` — the shared contract: `RegistryAdapter` ABC, `EntitySnapshot`,
  the canonical `PublicSignal`, and the `SnapshotDiff` / `diff_snapshots()`
  pattern. (Built in PR #14.)
- `cost.py` — the free-vs-paid layer on top: `SourceCost` / `AdapterStatus`
  enums, `SourceUnavailableError`, and the `CostMixin` every adapter combines
  with `RegistryAdapter`.
- one carcass module per still-unbuilt source — full metadata + docstring; the async
  `fetch` / `fetch_signals` are unimplemented.
- `registry.py` — the single catalogue (`REGISTRY`, `usable_adapters()`,
  `skipped_adapters()`, `catalogue()`).

A carcass fails loudly and *differently* depending on intent:

| Source kind | `fetch()` / `fetch_signals()` raises | Meaning |
|---|---|---|
| Free / free-tier (`PLANNED`) | `NotImplementedError` | to be built |
| Paid / restricted (`SKIPPED`) | `SourceUnavailableError` | will **not** be built |

So "not built yet" can never be confused with "skipped on purpose".

---

## The free-vs-paid decision

Hard requirement: **only sources that are 100% free / usable right now get
implemented.** Anything without a sustainable free tier is marked `PAID` and
skipped — and skipped in code, not just on paper.

The whole decision collapses to one invariant (enforced by a unit test):

```
status == SKIPPED   <=>   cost == PAID
status == PLANNED   <=>   cost == FREE or FREEMIUM
```

### Catalogue

| Source | What it provides | Cost | Key? | Decision |
|---|---|---|---|---|
| **ZEFIX** | Swiss commercial register: name, legal form, seat, status, purpose (Zweck), SHAB mutation log | FREEMIUM | yes⁰ | ✅ BUILT |
| **GLEIF** | Global LEI: name, status, jurisdiction, parent/children ownership graph | FREE | no | ✅ BUILT |
| **OpenSanctions** | OFAC/EU/UN sanctions + PEP screening with match scores | FREEMIUM | yes¹ | ✅ BUILT (key optional) |
| **GDELT 2.0** | Global news article lists + volume time-series (free news feed) | FREE | no | ✅ BUILT |
| **Event Registry** | News clustered into de-duplicated *events*, primary news source (hackathon key) | FREEMIUM³ | yes | ✅ BUILT (key-gated) |
| **Firecrawl** | Live website → markdown (current page content) | FREEMIUM | yes² | ✅ BUILT (key-optional) |
| **Wayback** | Historical website snapshot at the onboarding date | FREE | no | ✅ BUILT |
| **WHOIS / RDAP** | Domain age + registrant change | FREE | no | ✅ BUILT |
| **OpenCorporates** | Officers / directors in non-LEI jurisdictions | PAID | yes | ⛔ SKIP |
| **Crunchbase** | Funding rounds, investors, amounts | PAID | yes | ⛔ SKIP |

⁰ ZEFIX: free, but the ZefixPublicREST API requires a **free registered
Basic-auth account** (verified live — `401 WWW-Authenticate: Basic` without
credentials), so it is FREEMIUM, not FREE. The no-auth path is the daily ZEFIX
*Open Data* bulk dump (name-index snapshot, not live detail). ZEFIX does **not**
expose officers / board members / UBOs — those are in the cantonal registers.
The adapter (`sources/zefix.py`) is implemented against the live OpenAPI schema
(`POST /company/search` → `CompanyShort[]`, `GET /company/uid/{uid}` →
`CompanyFull[]`; `legalForm` is a nested `{de,fr,it,en}` map, `status` ∈
{ACTIVE, BEING_CANCELLED, CANCELLED}). Credentials come from
`ZEFIX_USERNAME`/`ZEFIX_PASSWORD`; with none set the adapter degrades gracefully
(`fetch → None`, `fetch_signals → []`) so the engine still runs. Engine wiring
(aggregator, score floor, synthetic scenario, UI badge) is tracked separately in
the ROADMAP use-case close-out tasks.
¹ OpenSanctions: the hosted `yente` API at `api.opensanctions.org` works
**unauthenticated** for non-commercial use (tighter rate limits). A key
(`OPENSANCTIONS_API_KEY` env var, sent as `Authorization: ApiKey …`) unlocks
higher limits. The adapter always attempts the API — it does **not** silently
skip when no key is set, unlike Event Registry. Commercial use of the data
needs a paid bulk-data licence — flag for production.
² Firecrawl: cloud free tier ~1,000 pages/month (no card); self-host is AGPL-3.0.
The adapter (`sources/firecrawl.py`) is implemented with a three-tier fallback
ladder so the key is **optional**: with `FIRECRAWL_API_KEY` set it scrapes the
cloud `/scrape` endpoint (clean markdown, JS-rendered); without a key it falls
back to a plain `httpx.GET` + stdlib HTML-to-text strip (zero cost, no extra
dependency); if the page is unreachable it returns an empty-`website_text`
snapshot rather than `None`. `fetch` only returns `None` when no `domain` is
supplied. The caller injects the customer's `domain` (from
`EntitySnapshotDB.extra`) as a keyword argument — the adapter never reads the DB.
`fetch_signals` is a deliberate no-op: business-model drift is detected by
`drift/business_model.py`, which embeds this adapter's `website_text` against the
Wayback onboarding snapshot (cosine distance ≥ 0.35 → `business_model_change`).
³ Event Registry: previously treated as paid (one-time trial allowance only). The
SwissHacks 2026 hackathon provides a full-access key (2,500 req/day), making it
FREEMIUM and fully implemented. When `EVENT_REGISTRY_API_KEY` is set it runs as
the primary news source; when absent it returns `[]` gracefully and GDELT is the
always-on free fallback. The two adapters complement each other — GDELT covers
free baseline article counts; Event Registry adds event-level de-duplication and
structured sentiment.

### Why each skip is safe (coverage is not lost)

| Skipped (paid) | Use cases | Free source that covers it |
|---|---|---|
| OpenCorporates | 3, 4, 5, 7 | **GLEIF** entity-level ownership (parent/child LEIs) + **ZEFIX** company fields. ⚠️ Natural-person **officers/directors** are a real gap — no free source (incl. ZEFIX) exposes them; entity-level UBO only. |
| Crunchbase | 6 | **Event Registry** (structured funding articles) + **GDELT** (free fallback) |

Net: **8 adapters to run (all 8 built — GLEIF, ZEFIX, Event Registry, OpenSanctions, Wayback, WHOIS/RDAP, Firecrawl, GDELT — 0 carcasses),
2 skipped.** No use case is fully dropped; officer/director-level resolution
(part of Cases 3/5) is degraded to entity-level ownership only — the one
capability lost by skipping the paid OpenCorporates. Event Registry is the
key-gated primary news source; GDELT remains the always-on free fallback.

---

## The adapter contract

Each source combines `CostMixin` (cost metadata) with `RegistryAdapter` (the
`base.py` contract) and implements two async methods:

```
async fetch(drift_id, name, **kwargs) -> EntitySnapshot | None
async fetch_signals(drift_id, name, since_month=0, **kwargs) -> [PublicSignal]
```

- `fetch` returns the source's current canonical `EntitySnapshot` (or `None` if
  the entity isn't in that source). The service layer stores it via
  `db.kyc_baseline.store_snapshot` and compares it to the onboarding baseline
  with the module-level **`diff_snapshots(baseline, current)`** → `[SnapshotDiff]`
  (each carrying a `drift_signal_type` and `severity` routed to a use case:
  `name_changed`, `jurisdiction_changed`, `dissolution_status_changed`,
  `ubo_added`/`ubo_removed`, …).
- `fetch_signals` returns `PublicSignal`s directly — used by sources whose output
  isn't a registry diff: **OpenSanctions** (match-score hit), **GDELT** (BOCPD
  over the per-month article count), **Firecrawl + Wayback** (embedding cosine
  distance, via `drift/business_model.py`).

`EntitySnapshot` is the canonical shape (`legal_form`, `jurisdiction`,
`registered_address`, `dissolution_status`, `beneficial_owners`, `officers`,
`raw_data`, …). Scalar fields are optional — `None` means *"this source does not
report this field"* and two `None`s are never a change; the list fields are
set-diffed. `PublicSignal` carries `source_url` for the officer-UI citation; an
adapter's `record_url()` supplies the click-through link.

> **Two signal vocabularies — don't confuse them.** `diff_snapshots` emits
> **past-tense** routing keys on `SnapshotDiff.drift_signal_type`
> (`name_changed`, `jurisdiction_changed`, `dissolution_status_changed`,
> `ubo_added`/`ubo_removed`, …). The adapter `signal_types` metadata and
> `ADAPTER_SIGNAL_TYPES` use the **noun** form on `PublicSignal.signal_type`
> (`name_change`, `jurisdiction_change`, `status_change`, …). These are two
> deliberately separate namespaces — registry-diff routing keys vs. the public
> signal type shown on a card. When the future aggregator turns a `SnapshotDiff`
> into a `PublicSignal`, it must map `*_changed` → `*_change` explicitly.

---

## Build order (when the carcasses get filled in)

Mirrors the sprint plan in `source-integration-architecture.md` §12, restricted
to the free sources:

1. **Registry** — `zefix` (free Basic-auth account), `gleif` (no key); highest signal → Cases 4, 7, 8, 10, 3, 5
2. **Screening** — `opensanctions` (free non-commercial / self-host yente) → Cases 2, 5
3. **News** — `gdelt` (free baseline) + `event_registry` (key-gated enhancement, event-level de-duplication) → Cases 1, 6, 8, 10
4. **Web** — `whois` + `wayback` + `firecrawl` all built → Cases 8, 9, 10

Prerequisite for all of them: `db/kyc_baseline.py` to store/load the
`EntitySnapshot` baseline each adapter diffs against (see ROADMAP P1 §2).
