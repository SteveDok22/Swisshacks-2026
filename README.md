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

## Drift Engine — AMINA Challenge 4

> *"Sanctions lists tell you who became toxic yesterday. Drift velocity tells you who is becoming toxic right now."*

The Drift Engine extends Sentinel with early detection of **KYC drift** — slow structural
changes that quietly invalidate a customer's original risk profile (the explicit core of
AMINA's Challenge 4 brief).

### The reframe

A KYC profile is not a document. It is a **snapshot of the parameters of a stochastic
process** taken at onboarding. The customer is the process; the profile is a frozen
estimate. Drift is the divergence between the frozen declared model and the evolving
observed trajectory. The question changes from *"did something bad happen?"* to
*"has the generative process behind this customer's behavior changed?"* — a well-posed
statistical question with 50 years of theory behind it.

### Signal layers

| Layer | Signal | Method | Tier / Cost |
|---|---|---|---|
| 1 · Deterministic | Sanctions / PEP / watchlist | Exact + fuzzy matching | T0 · free |
| 2 · Adverse media | News mention severity | Embedding classifier | T1 · cents |
| 3 · Ownership topology | UBO changes, shell chains | Graph diff + personalized PageRank | T1 · cents |
| 4 · Behavioral drift | Transaction process vs baseline | **BOCPD** + drift velocity | T0 · free |
| 5 · Declared consistency | Stated profile vs observed flows | Statistical tests | T0 · free |
| 6 · Peer divergence | Distance from segment cohort | Embedding distance | T1 · cents |
| 7 · Active intelligence | VoI-ranked RFI + adversarial self-test | Claude reasoning | T2 · rare |

Cheap tiers run on 100% of the book daily; expensive reasoning fires only on the
uncertain/high band — AMINA's cost-awareness criterion as an architectural principle,
not a bolt-on.

### Mathematical core

**BOCPD** (Adams & MacKay, 2007) maintains a posterior over the run length r_t — the
number of observations since the last changepoint in the customer's transaction stream.
A collapse in the MAP run length means the generative process just changed. Threshold
rules catch *outliers*; BOCPD catches *regime change* — a customer who slowly raised
average volume from 5K to 9K never crosses a 10K threshold, but the distribution shift
is plainly visible to the run-length posterior.

**Drift velocity** — our signature metric:

```
Drift(t) = KL( P_baseline || P_current(t) )    accumulated divergence, bits
DV(t)    = d/dt Drift(t)                       drift velocity, bits per month
```

Rising velocity is the earliest precursor — it fires before the absolute divergence
crosses any sane alert threshold.

**Risk contagion** — personalized PageRank from newly flagged entities over the ownership
graph surfaces at-risk customers who carry **no direct flag of their own**.

### Validation results (synthetic scenario suite, ground truth known)

| Metric | Result | Target |
|---|---|---|
| Classification | 10/10 customers | — |
| Lead time before simulated sanctions hit | 2–7 months (median 5.5) | ≥ 3 months |
| False positives on stable customers | 0 of 6 | < 5% |

Scenarios: stable (control), volume creep, counterparty migration, corridor shift,
combined. Module: `backend/app/drift/` (`bocpd.py`, `velocity.py`, `simulator.py`).

### Drift Engine references

* Adams & MacKay (2007). *Bayesian Online Changepoint Detection.* arXiv:0710.3742.
* Page (1954). *Continuous Inspection Schemes.* Biometrika 41 — CUSUM.
* Kullback & Leibler (1951). *On Information and Sufficiency.* Ann. Math. Stat. 22.
* Page, Brin, Motwani & Winograd (1999). *The PageRank Citation Ranking.* Stanford.
* Howard (1966). *Information Value Theory.* IEEE Trans. SSC — VoI for RFI ranking.
* FATF (2023). *Guidance on Beneficial Ownership of Legal Persons.*
* FINMA Circular 2024/3. *Operational risks and resilience — banks.*

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
│   │   ├── api/v1/              # routers + endpoints
│   │   ├── core/                # config, logging
│   │   ├── db/                  # SQLModel + async session
│   │   ├── drift/               # Drift Engine: BOCPD, velocity, simulator
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
├── pitch/                        # Deck, demo script, onboarding, walkthrough
├── README.md                     # This file — single source of truth
├── BUILD_JOURNAL.md              # Day-by-day build log (all days + hotfix)
└── WRAP_UP.md                    # Pre-announcement checklist
```

---

## Tech stack

**Backend** — FastAPI · Pydantic v2 · SQLModel · aiosqlite · XGBoost · SHAP ·
DiCE · sentence-transformers · Anthropic SDK · sse-starlette · structlog · uv

**Frontend** — Next.js 15 · React 19 · TypeScript (strict) · Tailwind v3 ·
TanStack Query · Radix UI · Motion · Lucide icons · Geist + IBM Plex Mono

---

## Pitch materials

All presentation materials live in `pitch/`:

| File | Purpose | Audience |
|---|---|---|
| `deck.md` | 10-slide pitch deck (Marp) | Judges |
| `demo-script.md` | Second-by-second 3-minute demo flow | Presenter |
| `team-onboarding.md` | New team member first 30 minutes | Team |
| `code-walkthrough.md` | Architecture tour | Team / judges / interviewers |
| `announcement.md` | Team announcement templates | Team channels |

Convert the deck: install **Marp for VS Code** extension and export from the editor, or:

```bash
npm install -g @marp-team/marp-cli
marp pitch/deck.md --pdf --allow-local-files -o pitch/deck.pdf
```

---

## Team & credits

Built by **Stiven Ntoktorov** as the project backbone, with team contributions
incoming. Designed for the SwissHacks 2026 hackathon (Tenity, Zurich).

Architecture conversations and code review by Claude (Anthropic).

---

## Project stats

| | |
|---|---|
| **Backend** | 50 Python files · ~5,000 LOC |
| **Frontend** | 23 TS/TSX files · ~3,000 LOC |
| **API endpoints** | 19 |
| **Jurisdiction rule packs** | 4 (CH/EU/HK/AE, YAML-edited) |
| **Mock cases** | 18 (across 3 case types, 4 jurisdictions) |
| **Pitch documents** | 5 (deck, demo script, onboarding, walkthrough, index) |
| **Daily build journals** | 12 |
| **First Load JS** | 138 KB (Next.js bundle) |

---

## Roadmap

**Ready for hackathon day** (pre-built):
- ✅ Core risk scoring with XGBoost + SHAP
- ✅ DiCE counterfactuals
- ✅ Streaming Claude explanations (SSE)
- ✅ FINMA-compliant anonymization
- ✅ Four-jurisdiction rule engine
- ✅ Immutable audit trail
- ✅ Production-grade UI with error boundaries, retry logic, skeleton loaders
- ✅ Mock-mode fallback (works without API key)
- ✅ 18 demo-ready cases

**Hackathon weekend additions** (planned with team):
- 🔨 Voice biometric layer (if AMINA challenge is selected)
- 🔨 Julius Baer skin with PRIIP/MiFID compliance walkthrough
- 🔨 Ripple skin with RLUSD escrow integration
- 🔨 Real-time alert WebSocket subscriber
- 🔨 Audit Log UI page

The backend already supports all three case types via the same engine.
Adding new ones is hours, not days.

---

## License

Educational / hackathon use. Not for production deployment without further
review of dependencies, security model, and regulatory mapping.
