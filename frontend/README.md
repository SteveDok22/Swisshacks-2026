# Sentinel Frontend

Next.js 15 + TypeScript + Tailwind dashboard for the Risk Intelligence Platform.

## Run

```bash
# 1. Install dependencies (first time only)
npm install

# 2. Make sure backend is running on :8000 first
#    (in ../backend: uvicorn app.main:app --reload)

# 3. Start the dev server
npm run dev
```

Open http://localhost:3000

## How it connects to the backend

`next.config.mjs` proxies `/api/backend/*` → `http://localhost:8000/api/v1/*`.
So the frontend never hardcodes localhost and avoids CORS issues.

The backend MUST be running for the case queue to load.

## Stack

- Next.js 15 (App Router) + React 19
- TypeScript (strict)
- Tailwind CSS v3
- TanStack Query (data fetching)
- Radix UI (accessible primitives)
- Recharts (SHAP charts — Day 8)
- Motion (animations)
- Geist + IBM Plex Mono fonts

## Structure

```
src/
├── app/
│   ├── layout.tsx       Root layout + QueryProvider
│   ├── page.tsx         Main 3-pane workspace
│   └── globals.css      Design tokens + fonts
├── components/
│   ├── QueryProvider.tsx
│   ├── layout/Sidebar.tsx
│   ├── cases/
│   │   ├── CaseQueue.tsx        Risk-sorted case list
│   │   └── CaseDetailPanel.tsx  Detail view (expands Day 8)
│   └── ui/
│       ├── RiskBadge.tsx
│       └── RiskScore.tsx
├── lib/
│   ├── api.ts           Typed API client
│   └── utils.ts         Formatting + risk colors
└── types/
    └── api.ts           Types mirroring backend schemas
```
