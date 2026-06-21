## Summary

Makes the Drift Engine demo solid across **synthetic** and **live** modes, and adds genuinely-live entities backed by real external-API data (no synthetic stand-ins), with real, clickable source links throughout.

### Live entities (real APIs, responses cached to `backend/data/api_cache/` for offline replay)
| drift_id | Entity | Real data shown |
|---|---|---|
| drift-live-001 | **Temenos AG** | Real GLEIF ownership + real recent news (Bloomberg/Seeking Alpha) + **UC9 website-drift** (Wayback 2021 ↔ Firecrawl now, model2vec cosine + one-line AI summary, links to both versions) |
| drift-live-002 | **Rosneft Trading S.A.** | Real **OpenSanctions** critical hit (clickable `opensanctions.org/entities/…`) + real Rosneft news |
| drift-live-003 | **Wirecard AG** | Real adverse-media coverage of the fraud (UC1) |
| drift-live-004 | **WW International, Inc.** | Real **GLEIF name change** — `PREVIOUS_LEGAL_NAME` Weight Watchers → WW → name_change re-KYC floor (UC4/UC8) |
| drift-live-005 | **Rosneft Deutschland GmbH** | Real "related business under sanctions" — German subsidiary of OFAC-sanctioned Rosneft, itself on the live OpenSanctions list (UC3/UC5) |

### Key fixes & features
- **Docker keys**: `docker-compose` now loads `backend/.env.shared` (only `.env` was wired, so ER/OpenSanctions/Anthropic keys were empty in the container).
- **OpenSanctions scoring**: `/search` returns no score field — derive it from name similarity gated on sanction topics (`_derive_match_score`). Real hits now fire; a definitive match floors the drift score at 90 (`SANCTIONS_SCORE_FLOOR`).
- **Source links**: news links are **always a direct article URL or absent — never a Google-News search**. Live entities attach the real article URL (`EventRegistry.fetch_recent_news`, which retries a simplified core name so a real entity yields real coverage).
- **Hybrid live signals**: live entities use real registry/screening signals + real recent articles, falling back to a clearly-labelled `(modeled)` scenario narrative only when the live feed is empty.
- **UC9 website-drift**: Wayback (via the CDX API — the `/available` API is 429-blocked from a shared IP) + Firecrawl + `model2vec` (baked into the image, offline) → cosine distance + a one-line **LLM summary of what changed**, with links to the archived snapshot and the live site. The raw crawled text is intentionally not displayed.
- **LLM**: real `claude-sonnet-4-5` T2 adjudication + the website-diff summary, **disk-cached** (replayable offline; near-zero cost after the committed cache).
- **Caching**: GLEIF / Event Registry / OpenSanctions / Firecrawl / Wayback / WHOIS / Anthropic all disk-cache successful responses; `DiskCache` auto-disabled under pytest (fixed ~24 leaking adapter tests).
- **UX**: right-panel loading spinner; `DemoModeBadge` is per-entity mode-aware (shows **LIVE** on live entities) and shows an inline **AI LIVE** tag (case queue uses synthetic data but real Claude); `corridor_alert` label added.

### Synthetic cast (unchanged, all 10 UCs) + UC8 fix
The 15-entity synthetic cast still covers every use case offline. The UC8 sanctioned-UBO entity (Bernina) now flags **critical** with a populated UBO-screening panel, mirroring the live OpenSanctions path.

## Test plan
- [x] `uv run pytest` — 974 passing; remaining failures are a pre-existing in-memory-DB isolation issue (`no such table: entity_snapshots`), not introduced here.
- [x] `/` drift workspace loads 15 synthetic + 5 live entities; clean score spread.
- [x] 5 live entities show real data, real source links, **0 Google-News links**.
- [x] WW International shows a real GLEIF `name_change`; Rosneft (Trading + Deutschland) show real OpenSanctions hits.
- [x] Temenos UC9 panel: AI summary + archived/live links (links resolve 200).
- [x] `/cases` works (10 clients, 19 cases); badge shows `SYNTHETIC · AI LIVE`.

> ⚠️ `backend/.env.shared` contains team hackathon keys (committed to this private repo by design). Rotate them after the event; do not push to a public fork.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
