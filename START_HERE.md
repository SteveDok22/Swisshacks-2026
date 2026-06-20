# Sentinel — Risk Intelligence Platform

**SwissHacks 2026 · AMINA Challenge 4: Dynamic Risk Profiling System**

Welcome. This drive contains the complete Sentinel project. Here is how to
navigate it.

---

## What this is

An AI system that spots financial risk early by combining real-time public
signals (news, sanctions, adverse media, ownership changes, funding events)
with internal KYC/AML data. Its core is **KYC drift detection** — catching the
slow structural changes that quietly invalidate a customer's original risk
profile, often months before a sanctions listing.

---

## Where to start (in order)

| Step | File | What you get |
|---|---|---|
| 1 | **`QUICKSTART.md`** | Run it locally in ~10 minutes (no API key needed) |
| 2 | **[`docs/drift-engine.md`](docs/drift-engine.md)** | The AMINA Challenge 4 approach, math, diagrams, and references |
| 3 | **`pitch/deck.md`** | The pitch deck (open with Marp or read the PDF) |
| 4 | **`pitch/demo-script.md`** | The 3-minute demo walkthrough |

## Technical documentation (docs/)

| Doc | Contents |
|---|---|
| **[docs/architecture.md](docs/architecture.md)** | System diagram, deployment topology, backend & frontend module maps |
| **[docs/drift-engine.md](docs/drift-engine.md)** | 7-layer pipeline, cost cascade decision tree, two-layer fusion |
| **[docs/flows.md](docs/flows.md)** | Use cases, officer investigation sequence, contagion discovery flow |
| **[docs/db-schema.md](docs/db-schema.md)** | ER diagram, enumerations, case lifecycle state machine |
| **[docs/api.md](docs/api.md)** | All 27 endpoints — methods, paths, response shapes |

---

## Fastest way to see it work

One command (full details in `QUICKSTART.md`):

```bash
docker compose up --build
```

Then open **http://localhost:3000** (API docs at **http://localhost:8000/docs**).

> **Runs offline, no API key required.** The AI explanations fall back to a
> built-in mock so the whole system is evaluable without internet or a key.

---

## What to look at in the running app

1. **Case Queue** (`/`) — the original compliance dashboard: risk scoring,
   SHAP explanations, counterfactuals, jurisdiction toggle, decision flow.
2. **Drift Engine** (`/drift`) — the AMINA Challenge 4 core. Open these
   customers to see the standout ideas:
   - **Viktor Antonov** vs **Maria Steiner** — same drift magnitude, but the
     causal layer separates risk from legitimate business growth.
   - **Pavel Novak** / **Irina Volkova** — the "slow-walker" detector: flagged
     for being *unnaturally smooth* while their environment moves.
   - **Helena Krause** — public adverse-media confirms internal drift
     (Confirmation Lift).
   - Drag the **timeline scrubber** to see drift flagged months before the
     simulated sanctions hit.

---

## What's inside

```
START_HERE.md            <- you are here
QUICKSTART.md            <- run instructions
README.md                <- product overview
backend/                 <- FastAPI + ML (27 endpoints)
frontend/                <- Next.js dashboard
pitch/                   <- deck, demo script, onboarding
docs/                    <- supporting docs
```

---

## Notes

- No `.env` file is included (no secrets shipped). The app runs in mock mode
  without one. To enable live Claude, copy `backend/.env.example` to
  `backend/.env` and add a key — optional.
- Dependencies aren't vendored — Docker installs them inside the images at
  build time (`docker compose up --build`), so the project stays portable.
- Built and tested on macOS (Apple Silicon); Linux and Windows work the same
  via Docker Desktop.

Thank you for reviewing Sentinel.
