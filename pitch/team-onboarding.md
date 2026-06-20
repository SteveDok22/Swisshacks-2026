# Team Onboarding — Sentinel

> Welcome to the team. This is your **first 30 minutes** with the project.
> By the end you'll understand what we built, run it locally, and know where to contribute.

---

## What we're building (60-second version)

**Sentinel** is an explainable AI dashboard for compliance officers at FINMA-regulated banks (AMINA, Julius Baer, Pictet).

The officer reviews flagged cases — voice transfer requests, suspicious trades, on-chain transactions. For each case, Sentinel shows:

- A **risk score** (XGBoost, 0-100)
- **Why** the score is what it is (SHAP feature contributions)
- **What would change it** (DiCE counterfactuals)
- **Under which jurisdiction's rules** (CH/EU/HK/AE toggle)
- **What goes to AI** (privacy split-view)
- A **decision flow** with immutable audit trail

This addresses the AMINA challenge directly (cross-jurisdictional compliance), and the architecture supports Julius Baer (investment recommendations) and Ripple (XRPL transactions) as additional case types.

---

## First — get it running (one command)

### Prerequisites

- **Docker Desktop** (with Compose v2) — `docker compose version`
- **Git** (you already have it if you cloned)

### Start everything

```bash
docker compose up --build
```

This builds and starts both containers with hot reload (backend on :8000,
frontend on :3000). The database is SQLite, auto-seeded on first start — no API
key needed. The backend log shows:
```
seed_completed     client_count=10  case_count=18
✓ Application startup complete.
✓ Uvicorn running on http://0.0.0.0:8000
```

### Verify

Open **http://localhost:3000**. You should see:

1. Welcome modal (dismiss it after reading)
2. Sidebar on left with "Sentinel" wordmark
3. Case Queue middle column with 18 cases
4. Right pane saying "Select a case to review"

Click **Marc Weber** (top of queue, score 100). The AI assessment should stream in word-by-word.

If anything failed — ping in Slack with the exact error.

### Run the tests

```bash
docker compose run --rm backend-tests
```

Runs the backend pytest suite in a container — no local Python needed.

---

## Next — read these 3 things (10 minutes)

In order:

1. **`README.md`** (root) — product overview, architecture diagram, quick start
2. **`pitch/deck.md`** — what we'll present to the judges
3. **`pitch/demo-script.md`** — the 3-minute demo, second-by-second

After this you'll understand **what** we're presenting and **how**.

---

## Then — explore the code (10 minutes)

Don't read everything. Start here:

### Backend tour

```
backend/app/
├── main.py                      # FastAPI app, lifespan (db init, ML load, seed)
├── api/v1/                      # 8 routers, 19 endpoints
│   ├── cases.py                 # Case queue + detail
│   ├── scoring.py               # POST /scoring/{case_id}
│   ├── explanations.py          # SSE streaming endpoint
│   └── ...
├── ml/
│   ├── registry.py              # Model lookup with fallback
│   ├── base.py                  # RiskModel (Strategy Pattern)
│   └── extractors/
│       └── social_engineering.py  # 16 features
├── services/
│   ├── risk_engine.py           # Orchestrator: score + rule overrides
│   ├── anonymizer.py            # Privacy by design
│   ├── counterfactual.py        # DiCE integration
│   └── jurisdiction.py          # YAML rule packs
└── jurisdictions/
    ├── CH.yaml                  # FINMA rules
    ├── EU.yaml                  # MiCA rules
    ├── HK.yaml                  # SFC rules
    └── AE.yaml                  # FSRA rules
```

**Start with**: `services/risk_engine.py` — this is the heart of scoring.

### Frontend tour

```
frontend/src/
├── app/
│   ├── layout.tsx               # Root layout + QueryProvider
│   ├── page.tsx                 # 3-pane workspace
│   └── about/page.tsx           # GitHub showcase page
├── components/
│   ├── layout/Sidebar.tsx       # Left nav
│   ├── cases/
│   │   ├── CaseQueue.tsx        # Risk-sorted list
│   │   ├── CaseDetailPanel.tsx  # Right pane orchestrator
│   │   ├── StreamingExplanation.tsx  # SSE typing effect
│   │   ├── SHAPViewer.tsx
│   │   ├── CounterfactualsViewer.tsx
│   │   ├── JurisdictionSelector.tsx
│   │   ├── PrivacyPanel.tsx
│   │   └── DecisionBar.tsx
│   └── ui/                      # RiskBadge, RiskScore
├── lib/
│   ├── api.ts                   # Typed API client
│   ├── useStreamingText.ts      # SSE hook
│   └── utils.ts                 # Formatting + risk colors
└── types/api.ts                 # Types mirroring backend schemas
```

**Start with**: `components/cases/CaseDetailPanel.tsx` — the whole right side hangs off this.

---

## Where you can contribute

Pick what fits your strength. Each line is roughly a half-day of work.

### If you do backend / ML

- **Train Julius Baer model** — `ml/extractors/investment_recommendation.py` (skeleton ready, just train XGBoost on synthetic allocation drift data)
- **Train Ripple model** — same pattern for XRPL transactions
- **Voice biometric layer** — `ml/extractors/voice_authenticity.py` (Resemblyzer + cosine similarity vs baseline)
- **Pytest coverage** — services/risk_engine, anonymizer, jurisdiction service have 0 tests right now

### If you do frontend / UI

- **Audit Log page** — `/audit` route, table of recent events, filter by case_id/event_type (backend ready: `GET /api/v1/audit`)
- **Live Alerts page** — `/alerts` route, WebSocket subscriber for new critical cases (backend needs `/ws/alerts` endpoint)
- **Mobile responsive** — current design is desktop-first, queue + detail need mobile layout
- **Dark mode** — design tokens in `tailwind.config.ts` are ready, just need `dark:` variants

### If you do design / pitch

- **Screenshots** — open dashboard at different cases, capture for `pitch/screenshots/`
- **Pitch deck polish** — convert `pitch/deck.md` to Keynote/PPT, add transitions
- **Demo recording** — screen capture of full demo flow, 3 min, for backup

### If you do DevOps

- **Docker Compose hardening** — current `docker-compose.yml` is dev-only, add prod profile
- **CI/CD** — GitHub Actions: run pytest + npm run build on PR
- **Deploy preview** — Vercel for frontend, Fly.io for backend, demo URL for jury

---

## Conventions we use

**Python**:
- `from __future__ import annotations` at the top of every file
- Type hints **everywhere**, no `Any` unless necessary
- `async def` for anything that touches DB or external API
- Logging via `structlog` (`logger = get_logger(__name__)`), structured key=value

**TypeScript**:
- Strict mode on, no `any`
- API types live in `src/types/api.ts`, mirror backend Pydantic
- Components stay under 200 lines — if growing, split
- Tailwind classes via `cn()` helper for conditional logic

**Commits**:
- Verb-first, imperative: `Add jurisdiction comparison endpoint`, not `Added` or `Adding`
- Short title (< 60 chars), body for context if needed
- Reference: Day N changes go into `DAY_N_GUIDE.md` first, then commit

**Branches**:
- `main` — always demo-ready
- `feature/<short-name>` — work in progress
- Open PR, get one review, merge with squash

---

## Stuck? Read these in order

1. **Error in browser console** → DevTools → Network tab → check the failing request
2. **Backend not starting** → `docker compose logs backend` (model-file and startup errors show here)
3. **Frontend not building** → rebuild: `docker compose up --build`
4. **Strange data** → `docker compose down -v` wipes the `backend_data` volume; the DB re-seeds on the next `docker compose up`
5. **Nothing else worked** → DM Stiven, screenshot + `docker compose logs`

---

## What you should know about Stiven (lead)

- Builds in Python primarily, full-stack capable
- Prefers explicit step-by-step over clever one-liners
- Reviews PRs same day usually
- Slack/Discord works, email for non-urgent
- Time zone: CET (Zurich)

---

## Project decisions log

Quick context on **why** things are the way they are:

- **SQLite (not Postgres)** — hackathon constraint, easy to ship. Migration path ready.
- **Next.js (not Vite/CRA)** — App Router gives us SSR + API routes for free; rewrites for API proxy avoid CORS pain
- **Tailwind v3 (not v4)** — v4 still has breaking changes, we need stability
- **Custom components (not shadcn as-is)** — generic shadcn UI = generic AI aesthetic. We're going for Swiss institutional.
- **Mock mode default** — demos must work offline at the venue (wifi sometimes flaky)
- **No tests in MVP** — controversial, but every minute spent on test infra is a minute not on demo polish. We'll add tests on Monday.

---

## You're good. Welcome.

If you read this far — you've already spent 30 minutes more than 80% of hackathon team members do on onboarding. That pays off in the next 48 hours.

Open Slack, say "Onboarded, ready to grab X" where X is from the contribute list above. Let's build.
