# Implementation Status

Sentinel · Drift Engine — [AMINA Bank · SwissHacks 2026 · Challenge 4](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md).

A snapshot of what's built. The technical detail lives in the wiki — start at the
[README](README.md), then [docs/](docs/) (architecture, drift-engine, use-cases,
sources, live-entities, api, data-model).

---

## Judging criteria

| Criterion | Weight | Status |
|---|---|---|
| **AI Intelligence Quality** | 25% | Strong — 9 analysis layers (changepoint, velocity, contagion, causal, stability, dormancy, business-model, public-intel) fused with confirmation lift + regulatory floors |
| **Cost Efficiency** | 20% | 3-tier cascade (rules → ML → Claude); per-scan tier counts, real-vs-cached T2 calls, and an LLM-on-everything baseline; ~94% cheaper |
| **UX & Explainability** | 20% | Verdict-first drift workspace, per-layer breakdown, source-linked signals, UC9 website-diff, time-travel replay |
| **Compliance & Safety** | 20% | Append-only audit trail (seeded with a ~97-entry compliance history), DecisionBar (HITL), source citations, jurisdiction rules |
| **Engineering & Architecture** | 15% | Modular engine, clean REST API, async, two-mode (synthetic/live), disk-cached adapters, unit + BDD tests |

---

## Use-case coverage — 10/10

All ten AMINA signals are covered by the deterministic synthetic cast, and most
are also proven by real-data **live entities**. The authoritative entity-by-entity
map (signal · layer · synthetic entity · live entity · analogue) is in
**[docs/use-cases.md](docs/use-cases.md)**. Summary: UC1 (Helvetia Pharma / live
Wirecard + Temenos), UC2 (Léman FX / live Rosneft Trading), UC3 (Alpine + Castor /
live Rosneft Deutschland), UC4 (Glarnisch / live **WW International**, real GLEIF
rename), UC5 (Bernina + Castor / live Rosneft Trading + Deutschland), UC6 (causal
scale-jump), UC7 (Rhône Capital), UC8 (Bernina / live GLEIF UBO chains), UC9
(HelvetiaX / live **Temenos** Wayback↔Firecrawl), UC10 (Lattice Labs).

---

## What's built

- **Drift engine** — 9 layers in `backend/app/drift/` (`bocpd`, `velocity`,
  `contagion`, `causal`, `stability`, `dormancy`, `business_model`, `public_intel`,
  `cascade`) + `timetravel`; fused score with re-KYC (50) and sanctions (90) floors.
- **Source adapters** — 8 free/freemium adapters (GLEIF, ZEFIX, OpenSanctions,
  Event Registry, GDELT, Wayback, WHOIS/RDAP, Firecrawl), all wired and disk-cached;
  2 paid sources (OpenCorporates, Crunchbase) intentionally skipped.
- **Two modes** — offline synthetic book (15 entities) + 5 live entities
  (`mode="live"`) scored on real GLEIF / OpenSanctions / news / website data, with
  responses cached to disk for offline replay; hybrid signal fallback.
- **LLM** — real `claude-sonnet-4-5` T2 adjudication + the UC9 website-diff summary,
  disk-cached (mock when no key / `ANTHROPIC_FORCE_MOCK=1`).
- **Cost cascade** — T0 rules → T1 ML → T2 Claude with a live cost meter.
- **Time-travel replay** — no-look-ahead as-of analysis (BDD-pinned).
- **Compliance** — append-only audit log + DecisionBar; seeding populates 10
  clients, 19 cases, and a ~97-entry backdated audit trail (`db/seed_audit.py`).
- **API + UI** — ~30 REST endpoints across 10 routers; Next.js drift workspace,
  case queue, and audit log.

---

## Known limitations / next steps

- **ZEFIX** needs a free Basic-auth account; absent → degrades gracefully.
- **Wayback** `/available` is rate-limited from shared IPs, so the adapter uses the
  CDX API; the historical onboarding date is seeded as `20220101` for reproducibility.
- **Tests** — `docker compose run --rm backend-tests`: ~975 passing; 6 pre-existing
  failures are an in-memory test-DB isolation issue (`no such table: entity_snapshots`),
  not a product bug — the app runs on the file-backed DB.
- No CI/CD, RBAC, encryption-at-rest, or rate limiting (out of hackathon scope).
