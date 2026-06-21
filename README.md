# Sentinel — KYC Drift Engine

> Early detection of customer-profile drift for FINMA-regulated banks.
> **AMINA Bank · SwissHacks 2026 · Challenge 4 (Dynamic Risk Profiling).**

Traditional KYC takes a snapshot at onboarding and re-checks it once a year. Risk
doesn't wait for the annual review — a customer's business model, ownership,
jurisdiction, or counterparties can drift into a different risk profile months
before anything trips a threshold. **Sentinel watches that drift continuously**,
fuses **public signals** (news, sanctions, registries, websites) with **internal
bank data** (transactions, KYC baseline), and surfaces the change *with its
evidence and a recommended action* — early enough to act.

> *"Sanctions lists tell you who became toxic yesterday. Drift velocity tells you
> who is becoming toxic right now."*

It runs in two modes from one codebase: a fully **offline synthetic** demo (15
deterministic Swiss entities exercising all 10 use cases) and a **live** mode
where 5 real companies are scored against real GLEIF / OpenSanctions / news /
website data — cached to disk so the live demo also runs offline.

---

## Quick start

```bash
docker compose up --build          # backend :8000 · frontend :3000
```

Open **http://localhost:3000**. No API keys required — the default is the offline
synthetic demo, and the 5 live entities replay from committed response caches.
Run the test suite with `docker compose run --rm backend-tests`.

Configuration, live mode, and the demo walkthrough: **[docs/getting-started.md](docs/getting-started.md)**.

---

## What it does

- **9-layer drift engine** — Bayesian changepoint detection, drift velocity,
  ownership contagion, causal analysis (risk vs benign), suspicious stability,
  dormancy break, business-model (website) drift, and a public-intelligence layer
  — fused by *confirmation lift* into one **0–100 score** with mandatory
  regulatory floors. See [drift-engine.md](docs/drift-engine.md).
- **Public + internal fusion** — 8 free/freemium source adapters (GLEIF, ZEFIX,
  OpenSanctions, Event Registry, GDELT, Wayback, WHOIS, Firecrawl) feed the same
  engine as the internal transaction data; every signal carries a real, clickable
  source link.
- **Cost-aware cascade** — T0 rules (free) → T1 ML → T2 Claude, so the expensive
  LLM only runs on genuinely uncertain cases (~94% cheaper than LLM-on-all).
- **Explainable & compliant** — per-layer score breakdown, time-travel replay
  (no look-ahead), an append-only audit trail seeded with a realistic compliance
  history, and a UC9 website-drift panel that diffs a company's onboarding website
  (Wayback) against its current site (Firecrawl) with a one-line AI summary.
- **Two modes, one engine** — `EXTERNAL_APIS_ENABLED` (default off) plus
  per-entity `mode="live"`; real responses and LLM completions are disk-cached so
  the live demo is fast and offline-reproducible.

All 10 AMINA use cases are covered — see **[use-cases.md](docs/use-cases.md)** for
the entity-by-entity map.

---

## Documentation

The README is intentionally short. Details live in **[docs/](docs/)**:

| Page | What's in it |
|---|---|
| [getting-started.md](docs/getting-started.md) | Run it, configure modes, populate caches, demo walkthrough |
| [architecture.md](docs/architecture.md) | System design, two-mode data flow, services, caching, deployment |
| [drift-engine.md](docs/drift-engine.md) | The 9 analysis layers, score fusion, regulatory floors, the cost cascade |
| [use-cases.md](docs/use-cases.md) | The 10 AMINA use cases ↔ which entity/scenario proves each |
| [sources.md](docs/sources.md) | The 8 source adapters, free-vs-paid, caching, hybrid fallback |
| [live-entities.md](docs/live-entities.md) | The 5 live entities, two-mode mechanics, cache pre-warming |
| [api.md](docs/api.md) | REST API reference (10 routers, ~30 endpoints) |
| [data-model.md](docs/data-model.md) | DB tables, enums, seeding (clients, cases, audit trail) |
| [flows.md](docs/flows.md) | User & system workflows, sequence diagrams |
| [CHALLENGE_4_OVERVIEW.md](docs/CHALLENGE_4_OVERVIEW.md) | The AMINA brief, judging criteria, glossary |
| [CODE_ATTRIBUTION.md](docs/CODE_ATTRIBUTION.md) | Algorithm sources, libraries, regulatory references |

Pitch material (deck, demo script, code walkthrough) lives in **[pitch/](pitch/)**.

---

## Stack

**Backend** — Python 3.12, FastAPI, Pydantic v2, SQLModel/SQLite, NumPy/SciPy,
NetworkX, XGBoost + SHAP + DiCE, model2vec (pure-NumPy embeddings, no torch),
Anthropic SDK, `uv`.
**Frontend** — Next.js 15, React 19, TypeScript, Tailwind, TanStack Query, SSE.
**Run** — Docker Compose: `backend` (:8000), `frontend` (:3000), `backend-tests`.

Validation: hypotheses **H1–H4** (early detection, velocity-as-leading-indicator,
contagion, cost-efficiency) have executable tests in `backend/tests/`; the
Time-Travel replay's no-look-ahead guarantee is pinned by a BDD feature. See
[drift-engine.md](docs/drift-engine.md#validation).

---

## Credits

**Author & architect:** Stiven Ntoktorov — Full-Stack Developer (FinTech/ML),
Zürich. Built with AI pair-programming (Anthropic Claude) for implementation and
review; architecture, algorithm selection, and validation directed by the author.
Algorithm and regulatory sources: **[CODE_ATTRIBUTION.md](docs/CODE_ATTRIBUTION.md)**.

AMINA Bank · SwissHacks 2026 · Challenge 4 · hosted by Tenity, Zürich.

> All customer data is **synthetic**. The 5 live entities are real *public*
> companies scored against *public* data sources for demonstration only — the
> repo contains no real customer information.
