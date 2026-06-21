# Live Entities — Real API Data in the Demo

Sentinel supports a **mixed-mode book**: most drift subjects and cases use
deterministic synthetic data, while specially-marked entities use **real
external API calls** whose responses are cached to disk and committed to the
repo.

## How It Works

```
SyntheticCustomer.mode = "live"   →  real adapters fire (GLEIF, Event Registry,
                                      OpenSanctions, Wayback, Firecrawl)
SyntheticCustomer.mode = "synthetic" (default)  →  deterministic mock signals
```

The per-entity check is in `backend/app/drift/service.py`:

```python
if settings.external_apis_enabled or cust.mode == "live":
    signals = gather_public_signals_sync(cust.drift_id, cust.name)
```

## Cache System

All external HTTP responses are written to **`backend/data/api_cache/`**:

```
backend/data/api_cache/
  gdelt/             ← GDELT article + timeline DataFrames
  gleif/             ← LEI records + name-lookup results
  event_registry/    ← Event Registry event/article batches
  opensanctions/     ← sanctions search results
```

Cache files are **committed to the repo** (the directory is bind-mounted in
`docker-compose.yml`).  On subsequent runs the engine reads from cache — no
live network call is needed, so the demo works fully offline.

Write-through behaviour: a cache miss triggers a live call, the response is
saved immediately, and the next run is instant.

## Current Live Entities

### Drift: Temenos AG (`drift-live-001`)

Real Swiss banking-software company (SIX: TEMN, ~CHF 2 B market cap).  In
February 2023 Hindenburg Research published an adverse short-seller report;
the CEO resigned weeks later.  GDELT and Event Registry return **real adverse-
media signals** for the Hindenburg cluster; GLEIF provides the real ownership
structure.

| Field | Value |
|-------|-------|
| `drift_id` | `drift-live-001` |
| `name` | Temenos AG |
| `domain` | temenos.com |
| `scenario` | `news_spike` (drives synthetic behavioural baseline) |
| `mode` | `live` |

### Case: RLUSD 4.2 M — Ahmed Al-Rashid (`55555555-5555-5555-5555-555555555501`)

XRPL transaction to an unresolved VASP in a FATF grey-list jurisdiction
(Pakistan), with Travel Rule data absent and a dormant-account reactivation
pattern.  Matches documented AML typologies (FATF 2023, case ref. TF-2023-0041).

## Populating the Cache (first run / new PC)

On **first startup** after a clean clone the cache may be empty (if you have not
yet committed populated files).  To fill it:

1. Set the required keys in `backend/.env`:

```env
EXTERNAL_APIS_ENABLED=false        # leave false — per-entity mode handles it
EVENT_REGISTRY_API_KEY=<your key>  # register free at eventregistry.org
OPENSANCTIONS_API_KEY=<your key>   # optional; keyless works with rate limits
ANTHROPIC_API_KEY=<your key>       # for T2 LLM adjudication
```

2. Restart the backend — it will call the real APIs for `drift-live-001` on the
   first `/drift/subjects` request and save responses to
   `backend/data/api_cache/`.

3. Commit the populated cache files:

```bash
git add backend/data/api_cache/
git commit -m "chore(cache): populate live-entity API cache"
git push
```

After that the demo runs fully offline — no keys needed on the demo laptop.

## Adding More Live Entities

1. In `backend/app/drift/simulator.py`, add a new `SyntheticCustomer` with
   `mode="live"` and set `domain` to the company's website.

2. Restart the backend — the entity will appear in the drift list with a
   **LIVE** badge and use real API signals.

3. Commit the newly written cache files so subsequent runs are offline.
