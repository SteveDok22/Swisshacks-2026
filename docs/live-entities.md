# Live Entities — Real API Data in the Demo

Sentinel runs a **mixed-mode book**: most drift subjects use deterministic
synthetic data, while five subjects marked `mode="live"` are scored against
**real external APIs**. Those responses are cached to disk and committed to the
repo, so the live demo also runs fully offline.

## How it works

Each subject in `generate_book()` (`backend/app/drift/simulator.py`) carries a
`mode`. The per-entity gate in `backend/app/drift/service.py` is:

```python
if settings.external_apis_enabled or cust.mode == "live":
    signals = gather_public_signals_sync(cust.drift_id, cust.name)
```

So a single entity can be live even when the global `EXTERNAL_APIS_ENABLED`
switch is off (the default). The synthetic subjects keep using the deterministic
generator; only the five live entities reach the network — and only on a cache
miss.

## The five live entities

| `drift_id` | Company | Real data shown | UCs |
|---|---|---|---|
| `drift-live-001` | **Temenos AG** (`temenos.com`) | Real GLEIF ownership + real recent news, and **UC9 website-drift**: the real 2021 Wayback snapshot vs the current Firecrawl scrape, model2vec cosine ≈ 0.76, a one-line LLM "what changed" summary, and links to both the archived and live site. | UC1, UC9 |
| `drift-live-002` | **Rosneft Trading S.A.** | Real **OpenSanctions** definitive hit with a clickable `opensanctions.org/entities/…` link, plus real Rosneft news. | UC2, UC5, UC8 |
| `drift-live-003` | **Wirecard AG** (`wirecard.com`) | Real adverse-media coverage of the €1.9 B collapse. | UC1 |
| `drift-live-004` | **WW International, Inc.** (`ww.com`) | Real **GLEIF legal-name change** — `PREVIOUS_LEGAL_NAME` "Weight Watchers International, Inc." → "WW International, Inc." — which fires the re-KYC name floor; plus real news. | UC4, UC8 |
| `drift-live-005` | **Rosneft Deutschland GmbH** | Real OpenSanctions hit; its GLEIF ultimate parent is sanctioned Rosneft — a "related business under sanctions". | UC3, UC5 |

These are real **public** companies scored against **public** data sources for
demonstration only. No real customer data is involved.

## Hybrid signal model

Live entities combine three things:

1. **Live registry/screening signals** — GLEIF (ownership, legal-name change),
   OpenSanctions (sanctions/UBO hits), WHOIS. These are authoritative and always
   carry a real, clickable source link.
2. **Real recent articles** — fetched from the live news source and attached with
   their actual article URLs.
3. **Modeled fallback** — only when the live news feed returns nothing, a
   clearly labelled `(modeled)` scenario narrative fills in, so a live entity is
   never empty.

News links are always a direct article URL or nothing at all — **never** a
Google-News search.

## Cache system

Every external response is written under `backend/data/api_cache/`, one
subdirectory per source, and committed to the repo:

```
backend/data/api_cache/
  gleif/           event_registry/   opensanctions/   gdelt/
  wayback/         whois/            firecrawl/        anthropic/   ← LLM completions
```

- **Write-through**: a cache miss triggers a live call; the response is saved
  immediately, so the next read is instant and offline.
- **Committed**: the directory is bind-mounted in `docker-compose.yml`; once
  populated and committed, the live demo needs no network and no keys.
- **Disabled under pytest** (`API_CACHE_DISABLED` / `PYTEST_CURRENT_TEST`), so
  unit tests see their mocks, not stale disk data.

Two implementation notes:

- **Wayback** uses the **CDX API** (`web.archive.org/cdx/search/cdx`); the
  `/available` endpoint is aggressively 429-rate-limited from shared IPs.
- The KYC baseline seeds `onboarding_date = "20220101"`, so the UC9 historical
  lookup resolves to a stable ~2022 snapshot on every run.

## Pre-warming the cache

After a clean clone the cache may be empty. To populate it (requires the keys in
`backend/.env.shared` / `backend/.env`):

1. Open each live entity **twice** in the UI, or hit
   `GET /api/v1/drift/subjects/drift-live-00X` twice. The first call fires the
   real adapters and the LLM summary and writes the cache; the second is fast.
2. Commit the populated cache:

   ```bash
   git add backend/data/api_cache/
   git commit -m "chore(cache): pre-warm live-entity API cache"
   ```

After that the demo runs fully offline — no keys needed on the demo laptop.

## Adding a new live entity

1. In `backend/app/drift/simulator.py`, append a `SyntheticCustomer` with
   `mode="live"` and a `domain` set to the company's website.
2. Restart the backend — it appears in the drift list with a **LIVE** badge and
   uses real API signals.
3. Open it twice to populate the cache, then commit the new cache files so
   subsequent runs stay offline.

See **[sources.md](sources.md)** for the adapters, **[architecture.md](architecture.md)**
for the two-mode data flow, and **[use-cases.md](use-cases.md)** for the full
UC ↔ entity map.
