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

GLEIF (real HTTP, no key) and ZEFIX (real HTTP, free Basic-auth account; degrades
gracefully without credentials) are **implemented**. All other adapters remain
carcasses — no real network I/O yet:

- `base.py` — the shared contract: `RegistryAdapter` ABC, `EntitySnapshot`,
  the canonical `PublicSignal`, and the `SnapshotDiff` / `diff_snapshots()`
  pattern. (Built in PR #14.)
- `cost.py` — the free-vs-paid layer on top: `SourceCost` / `AdapterStatus`
  enums, `SourceUnavailableError`, and the `CostMixin` every adapter combines
  with `RegistryAdapter`.
- one carcass module per source — full metadata + docstring; the async
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
| **OpenSanctions** | OFAC/EU/UN sanctions + PEP screening with match scores | FREEMIUM | yes¹ | ✅ IMPLEMENT |
| **GDELT 2.0** | Global news article lists + volume time-series (free news feed) | FREE | no | ✅ IMPLEMENT |
| **Firecrawl** | Live website → markdown (current page content) | FREEMIUM | yes² | ✅ IMPLEMENT |
| **Wayback** | Historical website snapshot at the onboarding date | FREE | no | ✅ IMPLEMENT |
| **WHOIS / RDAP** | Domain age + registrant change | FREE | no | ✅ IMPLEMENT |
| **Event Registry** | News clustered into de-duplicated *events* | FREEMIUM³ | yes | ✅ IMPLEMENT (carcass, hackathon key) |
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
¹ OpenSanctions: hosted API needs a key and is metered; the data + the `yente`
matcher are **free for non-commercial use** and self-hostable. Commercial use
needs a paid bulk-data licence — flag for production.
² Firecrawl: cloud free tier ~1,000 pages/month (no card); self-host is AGPL-3.0.
³ Event Registry: previously treated as paid (one-time trial allowance only). The
SwissHacks 2026 hackathon provides a full-access API key, making it FREEMIUM and
usable. The adapter remains a carcass (`fetch`/`fetch_signals` not yet
implemented); GDELT serves as a free, key-less news fallback in the meantime.

### Why each skip is safe (coverage is not lost)

| Skipped (paid) | Use cases | Free source that covers it |
|---|---|---|
| OpenCorporates | 3, 4, 5, 7 | **GLEIF** entity-level ownership (parent/child LEIs) + **ZEFIX** company fields. ⚠️ Natural-person **officers/directors** are a real gap — no free source (incl. ZEFIX) exposes them; entity-level UBO only. |
| Crunchbase | 6 | **GDELT** (funding/expansion as news — weaker, no structured amount) |

Net: **8 adapters to build, 2 skipped.** No use case is fully dropped, but
officer/director-level resolution (part of Cases 3/5) is degraded to entity-level
ownership only — the one capability lost by skipping the paid OpenCorporates.
Event Registry is now PLANNED (hackathon key available); GDELT remains its free
fallback when the key is absent.

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

1. **Registry** — `zefix`, `gleif` (no key, highest signal) → Cases 4, 7, 8, 10, 3, 5
2. **Screening** — `opensanctions` (free non-commercial / self-host yente) → Cases 2, 5
3. **News** — `gdelt` + BOCPD on the article time-series → Cases 1, 6
4. **Web** — `firecrawl` + `wayback` + `whois` → Cases 8, 9, 10

Prerequisite for all of them: `db/kyc_baseline.py` to store/load the
`EntitySnapshot` baseline each adapter diffs against (see ROADMAP P1 §2).
