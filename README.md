# Sentinel — Risk Intelligence Platform

> Explainable AI for compliance officers in FINMA-regulated banks.

Built for **SwissHacks 2026** as a universal risk-scoring backbone that adapts
to multiple challenges — AMINA (social engineering defense), Julius Baer
(explainable investment recommendations), Ripple (XRPL transaction AML).

---

## What it does

A compliance officer reviews flagged cases — voice transfer requests,
suspicious trades, on-chain transactions. For each case, Sentinel provides:

1. **A risk score** (0-100) from an XGBoost model trained on behavioral signals
2. **A natural-language assessment** streaming from Claude, in plain English
3. **SHAP feature contributions** — which signals drove the score, with magnitudes
4. **Counterfactual scenarios** — what minimal changes would flip the decision
5. **Jurisdiction-aware action** — same case, different rules under FINMA / MiCA / SFC / FSRA
6. **A privacy-by-design audit trail** — exactly what data left the bank vs stayed local
7. **An immutable decision log** with override rationale

The officer either accepts the AI's recommendation or overrides with documented
reasoning. Every step is logged.

---

## Why this is different from a typical hackathon dashboard

Most teams will build SHAP + Claude + dashboard. Four things separate this:

| | Most teams | Sentinel |
|---|---|---|
| Explainability | SHAP | SHAP + **DiCE counterfactuals** |
| LLM input | Raw client data | **Anonymized pseudonyms + bucketed amounts** |
| Jurisdictions | Hardcoded | **YAML rule packs** (CH/EU/HK/AE) with live toggle |
| UX | Request → wait → response | **Server-Sent Events** streaming, live typing effect |

These aren't features bolted on — they're architectural decisions made because
AMINA operates under four regulators and ships AI that compliance officers
actually trust.

---

## Architecture overview

```
┌─────────────── Frontend (Next.js 15) ────────────────┐
│  Sidebar  │  Case Queue  │  Detail Panel              │
│           │              │  ├─ Streaming AI (SSE)     │
│           │              │  ├─ SHAP viewer            │
│           │              │  ├─ Counterfactuals        │
│           │              │  ├─ Jurisdiction toggle    │
│           │              │  ├─ Privacy split-view     │
│           │              │  └─ Decision bar (sticky)  │
└──────────────────────────┬───────────────────────────┘
                           │ /api/v1/*  (REST + SSE)
┌──────────────────────────┴───────────────────────────┐
│              Backend (FastAPI 0.115)                  │
│                                                        │
│  Risk Engine     →  XGBoost + SHAP                    │
│  Counterfactuals →  DiCE (Microsoft Research)         │
│  Jurisdictions   →  YAML rule packs (4 regulators)    │
│  Anonymizer      →  Pseudonyms + bucketed amounts     │
│  Claude Wrapper  →  Streaming + caching + mock mode   │
│  Audit Log       →  Append-only, immutable            │
└──────────────────────────┬───────────────────────────┘
                           │
                  SQLite (async, SQLModel)
              clients · cases · decisions · audit_log
```

**19 API endpoints**, **4 jurisdiction rule packs**, **persistent DB**,
**full mock-mode fallback** when no Anthropic API key is set.

---

## Quick start

You need: **Python 3.11+**, **Node.js 20+**, two terminals.

### Terminal 1 — Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or: uv pip install -r pyproject.toml
python -m app.ml.training train-social-engineering
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The first run trains the XGBoost model (5000 synthetic samples, ~15 seconds)
and seeds SQLite with 10 clients + 18 realistic cases.

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. A welcome modal walks you through the demo flow.

### Optional — Real Claude responses

The system runs in mock mode by default (deterministic placeholder responses).
For real Claude responses, create `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Demo flow (3 minutes)

1. **Open** the Marc Weber case (top of the queue, score 99/100)
2. **Watch** the AI assessment stream in word-by-word
3. **Scan** the SHAP factors — red bars push risk up, green bars pull it down
4. **Read** the alternative scenarios: "If destination weren't Russia..."
5. **Toggle** the jurisdiction selector — try AE (FSRA, strictest framework)
6. **Expand** the Data Handling panel — see exactly what gets sent to AI
7. **Decide**: Block (agree with AI) or Allow (override with rationale)

Decision is logged immutably to the audit trail at
`GET /api/v1/audit?event_type=decision_recorded`.

---

## Project structure

```
swisshacks-2026/
├── backend/                      # FastAPI + ML + DB
│   ├── app/
│   │   ├── api/v1/              # 8 routers, 19 endpoints
│   │   ├── core/                # config, logging
│   │   ├── db/                  # SQLModel + async session
│   │   ├── jurisdictions/       # YAML rule packs (CH/EU/HK/AE)
│   │   ├── ml/                  # XGBoost + SHAP + feature extractors
│   │   ├── schemas/             # Pydantic API schemas
│   │   ├── services/            # Business logic orchestrators
│   │   └── utils/               # Anonymizer
│   ├── tests/                   # Pytest
│   └── data/models/             # Trained .joblib artifacts
├── frontend/                     # Next.js 15 + Tailwind + TanStack
│   ├── src/
│   │   ├── app/                 # App Router pages
│   │   ├── components/          # Cases, UI, layout
│   │   ├── lib/                 # API client, hooks, utils
│   │   └── types/               # TypeScript mirrors of backend schemas
│   └── tailwind.config.ts       # Swiss institutional design tokens
└── DAY_N_GUIDE.md               # Daily build journals (1 through current)
```

---

## Tech stack

**Backend** — FastAPI · Pydantic v2 · SQLModel · aiosqlite · XGBoost · SHAP ·
DiCE · sentence-transformers · Anthropic SDK · sse-starlette · structlog · uv

**Frontend** — Next.js 15 · React 19 · TypeScript (strict) · Tailwind v3 ·
TanStack Query · Radix UI · Motion · Lucide icons · Geist + IBM Plex Mono

---

## Team & credits

Built by **Stiven Ntoktorov** as the project backbone, with team contributions
incoming. Designed for the SwissHacks 2026 hackathon (Tenity, Zurich).

Architecture conversations and code review by Claude (Anthropic).

---

## License

Educational / hackathon use. Not for production deployment without further
review of dependencies, security model, and regulatory mapping.
