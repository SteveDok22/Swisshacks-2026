# Quickstart — get Sentinel running in 10 minutes

Two terminals: one for the backend (API + ML), one for the frontend (dashboard).

**Prerequisites**: Python 3.11+, Node.js 20+.
Check: `python3 --version` and `node --version`.

> **No API key needed.** Sentinel runs fully in **mock mode** without an
> Anthropic API key and without internet — the AI explanations use a built-in
> fallback. Everything you need to evaluate the project works offline. (If you
> *do* want live Claude responses, copy `backend/.env.example` to
> `backend/.env` and add your key — optional.)

---

## 1. Clone

```bash
git clone <REPO_URL>
cd swisshacks-2026
```

---

## 2. Backend — Terminal 1

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # ~2 min (ML libraries)
python -m app.ml.training train-social-engineering   # ~15s, trains the model
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
seed_completed     client_count=10  case_count=18
Uvicorn running on http://0.0.0.0:8000
```

Leave this terminal running.

**Verify**: open http://localhost:8000/docs — interactive API docs (27 endpoints).

---

## 3. Frontend — Terminal 2 (new tab)

```bash
cd frontend
npm install      # ~1-2 min
npm run dev
```

You should see:
```
Ready in ~1s
Local: http://localhost:3000
```

**Open** http://localhost:3000 — a welcome modal walks you through the demo.

> The backend must be running first, or the dashboard shows "Failed to load cases".

---

## 4. Quick smoke test (Terminal 3, optional)

```bash
# Health
curl http://localhost:8000/health

# Drift Engine — the AMINA Challenge 4 core
curl -s -X POST http://localhost:8000/api/v1/drift/scan | python3 -m json.tool

# Risk-sorted drift customers
curl -s http://localhost:8000/api/v1/drift/customers | python3 -m json.tool | head -20
```

---

## What to look at first

1. **Dashboard** (localhost:3000) — click "Marc Weber" case, watch the AI explanation stream in, scroll through SHAP / counterfactuals / jurisdiction toggle.
2. **API docs** (localhost:8000/docs) — try the `drift` section: `/drift/scan`, `/drift/customers`, `/drift/contagion`.
3. **The Drift Engine spec** — [`docs/drift-engine.md`](docs/drift-engine.md) explains the AMINA Challenge 4 approach, math, and validation.

---

## If something breaks

| Problem | Fix |
|---|---|
| `Failed to load cases` in UI | Backend not running — start Terminal 1 first |
| `ModuleNotFoundError` | `pip install -r requirements.txt` again inside the venv |
| `next: not found` | `npm install` again in `frontend/` |
| Stale / weird data | `rm backend/data/risk_platform.db` then restart backend |
| Port 8000 busy | `uvicorn ... --port 8001` and set the same in `frontend/next.config.mjs` |

Stuck after that? Message me with the exact error + last 10 lines of the terminal.
