# SwissHacks 2026 — Risk Intelligence Platform

Universal risk scoring platform with explainable AI, built for SwissHacks 2026.

## Architecture

Modular system that adapts to multiple challenges:
- **AMINA**: Social engineering / deepfake defense
- **Julius Baer**: Explainable investment recommendations  
- **Ripple**: AML/risk scoring on XRPL transactions

## Stack

**Backend**: FastAPI · XGBoost · SHAP · DiCE · Anthropic Claude · sentence-transformers  
**Frontend**: Next.js 15 · TypeScript · Tailwind · shadcn/ui · Framer Motion · D3.js  
**Infra**: Docker Compose · uv · pnpm

## Quick start

```bash
# Start everything
docker compose up

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# Backend docs: http://localhost:8000/docs
```

## Project structure

```
swisshacks-2026/
├── backend/    # FastAPI + ML
├── frontend/   # Next.js
├── docker/     # Dockerfiles
└── scripts/    # Helpers
```

## Key differentiators

1. **Local-first AI** — Critical data processed locally, only anonymized features sent to LLM
2. **Streaming UX** — Real-time SSE responses, progressive UI rendering
3. **Counterfactual reasoning** — DiCE library for "what would change the decision"
4. **Adaptive jurisdiction layer** — FINMA / MiCA / SFC / ADGM rule packs
