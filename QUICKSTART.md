# Quickstart — run Sentinel with Docker

**Prerequisite**: Docker Desktop (with Compose v2). Check with `docker compose version`.

> **No API key needed.** Sentinel runs fully in **mock mode** without an
> Anthropic API key and without internet — the AI explanations use a built-in
> fallback. Everything you need to evaluate the project works offline. (If you
> *do* want live Claude responses, copy `backend/.env.example` to
> `backend/.env` and add your key — optional.)

---

## Run it

```bash
git clone <REPO_URL>
cd swisshacks-2026

docker compose up --build
```

- Frontend (dashboard) → http://localhost:3000
- Backend (API docs) → http://localhost:8000/docs

That single command builds and starts **both** containers with **hot reload**:

- edits in `backend/app/**` restart the API via uvicorn `--reload`
- edits in `frontend/src/**` refresh the dashboard via Next.js HMR

The SQLite database lives in the `backend_data` volume and is auto-seeded with
mock data on first start — no separate database container. Stop everything with:

```bash
docker compose down
```

> Production images (compiled, no source mounts) can still be built from the
> Dockerfile prod stages — e.g. `docker build --target runner ./frontend` — but
> local development uses the single `docker compose up` above.

---

## What to look at first

1. **Dashboard** (localhost:3000) — click "Marc Weber" case, watch the AI explanation stream in, scroll through SHAP / counterfactuals / jurisdiction toggle.
2. **API docs** (localhost:8000/docs) — try the `drift` section: `/drift/scan`, `/drift/customers`, `/drift/contagion`.
3. **The Drift Engine spec** — [`docs/drift-engine.md`](docs/drift-engine.md) explains the AMINA Challenge 4 approach, math, and validation.
