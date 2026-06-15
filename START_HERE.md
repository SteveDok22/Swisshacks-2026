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
| 2 | **`DRIFT_ENGINE_README.md`** | The AMINA Challenge 4 approach, math, and references |
| 3 | **`BUILD_JOURNAL.md`** | Day-by-day build history (how it was made) |
| 4 | **`pitch/deck.md`** | The pitch deck |
| 5 | **`pitch/demo-script.md`** | The 3-minute demo walkthrough |

---

## Fastest way to see it work

Open `QUICKSTART.md` and follow the two-terminal setup. In short:

```
# Terminal 1 — backend
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.ml.training train-social-engineering
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Then open **http://localhost:3000**.

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
DRIFT_ENGINE_README.md   <- AMINA Challenge 4 technical spec
BUILD_JOURNAL.md         <- full build history
backend/                 <- FastAPI + ML (26 endpoints)
frontend/                <- Next.js dashboard
pitch/                   <- deck, demo script, onboarding
docs/                    <- supporting docs
```

---

## Notes

- No `.env` file is included (no secrets shipped). The app runs in mock mode
  without one. To enable live Claude, copy `backend/.env.example` to
  `backend/.env` and add a key — optional.
- `node_modules/` and Python `.venv/` are not included — they are created by
  `npm install` and `pip install` so the project stays portable across
  machines.
- Built and tested on macOS (Apple Silicon). Linux and Windows work; on
  Windows use `.venv\Scripts\activate` to activate the virtualenv.

Thank you for reviewing Sentinel.
