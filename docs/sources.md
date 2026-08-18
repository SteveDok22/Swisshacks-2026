# Source Adapters

The Public Intelligence layer draws on external data sources and turns each
observed change into a `PublicSignal` the drift engine fuses with internal bank
data. This page is the catalogue: **what each source provides, whether it is free
and usable today, how it is cached, and the two we deliberately skip.**

All adapters live in `backend/app/sources/`. See
[drift-engine.md](drift-engine.md) for how their signals fuse into the score, and
[live-entities.md](live-entities.md) for how the 5 live entities use them.

---

## Decision rule: free only

**Only sources with a sustainable free tier are implemented.** Anything that
needs a paid plan is marked `PAID` and skipped — in code, not just on paper. The
rule collapses to one invariant, enforced by a unit test:

```
status == SKIPPED   <=>   cost == PAID
status == PLANNED   <=>   cost == FREE or FREEMIUM   (i.e. usable)
```

Net result: **8 adapters implemented and wired, 2 skipped.** No use case is fully
dropped (the one real gap — natural-person officers/directors — has no free
source anywhere; entity-level ownership via GLEIF covers the rest).

---

## The 8 implemented adapters

All eight are fully implemented (real HTTP), wired into the engine through the
aggregator, and **disk-cached** so the live demo replays offline.

| Source | Provides | Cost | Key | Use cases |
|---|---|---|---|---|
| **GLEIF** | LEI record, jurisdiction, status, ultimate-parent chain, direct children, `PREVIOUS_LEGAL_NAME` | FREE | none | 3, 4, 5, 8, 10 |
| **ZEFIX** | Swiss commercial register: legal name, legal form, seat, dissolution status, SHAB mutations | FREE¹ | account | 4, 7 |
| **OpenSanctions** | OFAC / EU / UN / SECO sanctions + PEP screening, with clickable entity URLs | FREEMIUM | optional² | 2, 5, 8 |
| **Event Registry** | De-duplicated news *events* + articles with sentiment — **primary news source** | FREEMIUM | yes³ | 1, 6, 10 |
| **GDELT** | Global news volume + article search — **news fallback** | FREE | none | 1, 6, 10 |
| **Wayback Machine** | Historical website snapshot at the onboarding date (UC9 "before") | FREE | none⁴ | 9 |
| **Firecrawl** | Current website → clean text (UC9 "after") | FREEMIUM | optional⁵ | 9, 10 |
| **WHOIS / RDAP** | Domain registrant, registration/age, registrant change | FREE | none | 8, 9 |

¹ **ZEFIX** — the live REST API needs a *free* registered Basic-auth account
(`ZEFIX_USERNAME`/`ZEFIX_PASSWORD`); without it the adapter degrades gracefully
(`fetch → None`, `fetch_signals → []`) and the engine still runs. ZEFIX exposes
company fields but **not** officers/UBOs (those are in cantonal registers).

² **OpenSanctions** — the hosted `yente` API works **unauthenticated** for
non-commercial use (tighter limits); `OPENSANCTIONS_API_KEY` (sent as
`Authorization: ApiKey …`) unlocks higher limits. The `/search` endpoint returns
no `score` field, so the adapter **derives a match score** from name similarity
(`difflib` ratio) *gated on the hit actually being a sanctions target* (its
`topics`/`target` flags) — this stops an incidental fuzzy name match from firing.
A definitive hit (≥ 0.85) → `sanctions` critical; 0.70–0.85 → high/probable. It
also screens UBO/officer names passed via the `ubo_names` kwarg (resolved from
the GLEIF ownership chain) and emits an `ownership_change` signal carrying
structured `meta` (screened name, matched entity, score), surfaced as
`DriftSubjectDetail.ubo_screening` (UC5/UC8).

³ **Event Registry** — the SwissHacks key gives full access (2,500 req/day). When
`EVENT_REGISTRY_API_KEY` is set it is the primary news source; when absent it
returns `[]` and GDELT takes over. `fetch_recent_news()` returns the latest real
articles (real title + real URL); the aggregator retries a *simplified core name*
(e.g. "Rosneft Trading S.A." → "Rosneft") so a real entity reliably yields real
coverage.

⁴ **Wayback** — fetches the onboarding-era snapshot via the **CDX API**
(`web.archive.org/cdx/search/cdx`), because the `/available` API is aggressively
429-rate-limited from a shared IP. `fetch_signals` is a no-op by design — the
signal is the *distance* to the current page (see UC9 below).

⁵ **Firecrawl** — key-optional three-tier ladder: cloud `/scrape` with a key →
plain-HTTP + stdlib HTML-strip without one → empty snapshot if unreachable. The
caller injects the customer's `domain`; the adapter never reads the DB.

### Skipped (paid) — coverage is not lost

| Skipped | Use cases | Free source that covers it |
|---|---|---|
| **OpenCorporates** | 3, 4, 5, 7 | GLEIF (entity-level ownership) + ZEFIX (company fields). Gap: natural-person officers — no free source exposes them. |
| **Crunchbase** | 6 | Event Registry (funding articles) + GDELT (fallback) |

Both remain metadata-only carcasses whose `fetch` raises `SourceUnavailableError`,
so "skipped on purpose" can never be confused with "not built yet"
(`NotImplementedError`).

---

## The adapter contract

Each adapter combines `CostMixin` (cost metadata, `cost.py`) with the
`RegistryAdapter` ABC (`base.py`) and implements two async methods:

```python
async fetch(drift_id, name, **kwargs) -> EntitySnapshot | None
async fetch_signals(drift_id, name, since_month=0, **kwargs) -> list[PublicSignal]
```

- **`fetch`** returns the source's current canonical `EntitySnapshot`
  (`legal_form`, `jurisdiction`, `dissolution_status`, `beneficial_owners`,
  `officers`, `raw_data`, …) or `None` if the entity isn't in that source. The
  service layer stores it and diffs it against the onboarding baseline with
  `diff_snapshots(baseline, current)` → `[SnapshotDiff]` (each carrying a routing
  key + severity: name change, jurisdiction change, dissolution, UBO added/removed).
- **`fetch_signals`** returns `PublicSignal`s directly — used by sources whose
  output isn't a registry diff: OpenSanctions (match-score hit), GDELT/Event
  Registry (news), and the Wayback↔Firecrawl comparator.

`base.py` is the shared contract; `registry.py` is the single catalogue
(`usable_adapters()`, `skipped_adapters()`); `cost.py` holds the `SourceCost` /
`AdapterStatus` enums and `SourceUnavailableError`.

> **Two signal vocabularies.** `diff_snapshots` emits past-tense routing keys
> (`name_changed`, `jurisdiction_changed`); the `PublicSignal.signal_type` shown
> on a card uses the noun form (`name_change`, `jurisdiction_change`). They are
> separate namespaces; the layer that turns a diff into a signal maps `*_changed`
> → `*_change` explicitly.

---

## Aggregator + hybrid fallback

`public_intel.gather_public_signals(drift_id, name)` (async) fans
`fetch_signals()` out to every `usable_adapters()` in parallel, catches
per-adapter errors, and returns a merged, time-sorted list.
`gather_public_signals_sync()` bridges it into the synchronous engine via a
dedicated thread, so it is safe under FastAPI's running loop. Adapter dispatch is
gated by `EXTERNAL_APIS_ENABLED`, but a per-entity `mode="live"` fires the real
adapters regardless (the 5 live entities).

**Hybrid fallback (live mode).** Registry/screening sources (GLEIF, OpenSanctions,
WHOIS) are reliable live, but the live *news* feeds frequently have no recent
coverage (rate limits, or the real adverse event predates the query window). So a
live entity uses:

1. Real registry/sanctions signals + **real recent articles** (real title + real
   URL) where available; then
2. a clearly-labelled **`(modeled)` scenario narrative** *only* when the live news
   feed is empty.

News signals therefore always link to a **direct article or carry no link at all
— never a search page**.

---

## UC9: Wayback ↔ Firecrawl website-drift comparator

Neither website adapter emits a signal alone; the signal is the **distance
between them** (`drift/business_model.py`):

1. Wayback recovers the onboarding-era `website_text` (via CDX).
2. Firecrawl recovers the current `website_text`.
3. `compare_business_model(...)` embeds both and emits a `business_model_change`
   signal when the cosine distance is **≥ 0.35** (severity `clip(0.20 + 1.30 ×
   distance, 0, 0.95)`), plus a one-line LLM "what changed" summary and links to
   both versions.

**Embedder — model2vec (`minishlab/potion-base-8M`), not torch.** A static
MiniLM-class distillation running on pure NumPy (~30 MB, no torch/onnx), baked
into the image for a genuinely offline comparison. Pluggable behind an `Embedder`
protocol. Degrade-never-raise: the comparator skips (machine-readable
`skipped_reason`: `"empty_text"` / `"no_embedder"`) and never raises into a scan.
Embeddings are cached by SHA-256 text fingerprint in `EntitySnapshotDB.raw_data`
so a re-scan of an unchanged page skips re-embedding.

---

## Disk cache

`core/api_cache.py` `DiskCache` is a per-service JSON cache under
`backend/data/api_cache/{service}/`:

- **Write-through** — a miss triggers the live call (when enabled + keyed), then
  the response is saved; the next read is instant and free.
- **Committed to the repo** — real GLEIF / Event Registry / OpenSanctions / GDELT
  / Wayback / WHOIS / Firecrawl responses *and* Anthropic LLM completions are
  committed, so the 5 live entities replay fully offline.
- **Disabled under pytest** (`PYTEST_CURRENT_TEST` / `API_CACHE_DISABLED`) so
  adapter unit tests see their mocked HTTP, not a stale cached value.

To (re)populate after editing a live entity: open its detail page (or hit
`/api/v1/drift/subjects/{id}`) twice, then commit `backend/data/api_cache/`.
