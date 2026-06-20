# Sentinel — Source Adapters (`backend/app/sources/`)

> The Public Intelligence layer (Layer 2) draws on external sources and turns
> each observed change into a `PublicSignal` the drift engine fuses with internal
> bank data. This document is the catalogue: **what each source provides, whether
> it is free and usable right now, and which ones we deliberately skip.**
>
> Companion to [`source-integration-architecture.md`](source-integration-architecture.md)
> (the pipeline design) and [`drift-engine.md`](drift-engine.md).

---

## Status: scaffolding (carcass)

This package currently ships the **contract and skeletons only** — no adapter
performs real network I/O yet:

- `base.py` — `RegistryAdapter` ABC, `EntitySnapshot`, the generic field-diff,
  the `SourceCost` / `AdapterStatus` enums, and `SourceUnavailableError`.
- one carcass module per source — full metadata + docstring; `fetch`/`normalize`
  are unimplemented.
- `registry.py` — the single catalogue (`REGISTRY`, `usable_adapters()`,
  `skipped_adapters()`, `catalogue()`).

A carcass fails loudly and *differently* depending on intent:

| Source kind | `fetch()` raises | Meaning |
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
| **ZEFIX** | Swiss commercial register: name, legal form, seat, status, mutation date | FREE | no | ✅ IMPLEMENT |
| **GLEIF** | Global LEI: name, status, jurisdiction, parent/children ownership graph | FREE | no | ✅ IMPLEMENT |
| **OpenSanctions** | OFAC/EU/UN sanctions + PEP screening with match scores | FREEMIUM | yes¹ | ✅ IMPLEMENT |
| **GDELT 2.0** | Global news article lists + volume time-series (free news feed) | FREE | no | ✅ IMPLEMENT |
| **Firecrawl** | Live website → markdown (current page content) | FREEMIUM | yes² | ✅ IMPLEMENT |
| **Wayback** | Historical website snapshot at the onboarding date | FREE | no | ✅ IMPLEMENT |
| **WHOIS / RDAP** | Domain age + registrant change | FREE | no | ✅ IMPLEMENT |
| **OpenCorporates** | Officers / directors in non-LEI jurisdictions | PAID | yes | ⛔ SKIP |
| **Event Registry** | News clustered into de-duplicated *events* | PAID³ | yes | ⛔ SKIP |
| **Crunchbase** | Funding rounds, investors, amounts | PAID | yes | ⛔ SKIP |

¹ OpenSanctions: hosted API needs a key and is metered; the data + the `yente`
matcher are **free for non-commercial use** and self-hostable. Commercial use
needs a paid bulk-data licence — flag for production.
² Firecrawl: cloud free tier ~1,000 pages/month (no card); self-host is AGPL-3.0.
³ Event Registry is technically freemium, but the free allowance is a **one-time
~2,000-token trial**, not a renewing tier — unusable for a live demo, so we treat
it as paid.

### Why each skip is safe (coverage is not lost)

| Skipped (paid) | Use cases | Free source that covers it |
|---|---|---|
| OpenCorporates | 3, 4, 5, 7 | **GLEIF** (ownership/parent-child) + **ZEFIX** (Swiss officers) |
| Event Registry | 1, 6, 8, 10 | **GDELT** (article lists + volume time-series, key-less) |
| Crunchbase | 6 | **GDELT** (funding/expansion as news — weaker, no structured amount) |

Net: **7 adapters to build, 3 skipped, 0 use cases dropped.** GDELT is the new
free addition that replaces the paid Event Registry as the news feed.

---

## The adapter contract

Every source is a `RegistryAdapter` and follows **fetch → normalize → diff**:

```
fetch(entity_id) -> raw dict
    normalize(raw) -> EntitySnapshot        # canonical, comparable view
        diff(baseline, current) -> [PublicSignal]   # only what changed
```

`fetch_and_diff(entity_id, baseline)` chains all three against the stored KYC
baseline, so the engine asks one question per source: *"what changed since
onboarding?"*

`EntitySnapshot` is the canonical shape (`legal_name`, `legal_form`,
`jurisdiction`, `registered_address`, `status`, `owners`, `domain`, …). Every
field except the ids is optional — `None` means *"this source does not report
this field"* and is never counted as a change.

The base class ships a **generic field diff**: it walks `field_rules`, emits a
`PublicSignal` for each changed canonical field, and treats `owners` as a set
(a newly added owner → `ownership_change`). Sources whose signal is not a field
comparison override `diff`:

- **OpenSanctions** — screens a name, returns a match-score hit (not a diff).
- **GDELT** — runs BOCPD over the per-month article count (a time-series).
- **Firecrawl + Wayback** — embedding cosine distance between onboarding and
  current website text (handled by `drift/business_model.py`).

`PublicSignal` (defined in `drift/public_intel.py`, shared with the existing
synthetic generator) now also carries `source_url` (citation for the officer UI)
and `raw_evidence` (the changed fields / match score behind the signal).

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
