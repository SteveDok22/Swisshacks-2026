# Team Announcement Templates

Шаблоны для оповещения команды о готовом MVP. Три варианта под разные каналы.

---

## Variant A: Slack / Discord (long form)

Лучше для основного team channel, где они **должны** прочитать. Чуть длиннее, но даёт полный контекст.

```
👋 Hey team — quick update on SwissHacks 2026.

I've been pre-building the project foundation over the past two weeks
so we can hit the ground running on hackathon weekend. Here's what's
ready for you to fork and build on:

**Sentinel** — Risk Intelligence Platform for FINMA-regulated banks.

Universal compliance dashboard that adapts to multiple challenges
(AMINA / Julius Baer / Ripple). The architecture supports all three
case types via the same engine — we pick the skin/extension on Saturday
based on which challenge we go for.

📦 **What's built right now**:
• ~30 API endpoints, ML pipeline (XGBoost + SHAP + DiCE counterfactuals)
• Next.js dashboard with streaming Claude explanations via SSE
• 4-jurisdiction rule engine (FINMA/MiCA/SFC/FSRA), YAML-editable
• FINMA-compliant anonymizer + immutable audit log
• 18 realistic mock cases across all case types
• Error boundaries, retry logic, skeleton loaders — demo-bulletproof

🎯 **What you'll do on the weekend** — depends on which challenge we
pick, but the engine is already there. Adding a new case type is hours,
not days.

🚀 **Start here** (15 min total):
1. Clone: `git clone <repo-url>`
2. Read: `pitch/team-onboarding.md` (30 min interactive guide)
3. Run locally — backend + frontend (instructions in README)
4. Open localhost:3000 — Welcome modal will walk you through demo flow

📄 **Pitch materials ready** in `pitch/`:
• 10-slide deck (Marp format, converts to PDF)
• Second-by-second 3-minute demo script
• Code walkthrough for architecture tours
• Q&A prep with judge questions

Feedback welcome. If something doesn't run locally — ping me with the
exact error and I'll fix it before the weekend.

Let's build something good. 🇨🇭
```

---

## Variant B: Slack / Discord (short form)

Если канал шумный или ты хочешь не overwhelmить — minimal version с ссылкой на onboarding.

```
👋 SwissHacks update: project foundation is ready.

**Sentinel** — compliance dashboard for AMINA / Julius Baer / Ripple
challenges. Universal engine, swap skins on Saturday based on challenge.

What's built: backend (~30 endpoints, ML pipeline, 4 jurisdictions),
frontend (Next.js dashboard, streaming AI, SHAP, counterfactuals),
18 mock cases, pitch deck, demo script.

Start: clone repo → read `pitch/team-onboarding.md` (30 min guide).

Questions: DM me or thread here.
```

---

## Variant C: Email (formal, for less-engaged team members)

Для случая если team member пропал из чата и нужно его подцепить.

```
Subject: SwissHacks 2026 — project ready for your review

Hi [Name],

Wanted to give you a heads-up before the hackathon weekend. I've been
pre-building the project foundation so we can hit the ground running
when the challenges are announced on Friday evening.

The project is called Sentinel — a compliance dashboard for FINMA-
regulated banks. It addresses the AMINA, Julius Baer, and Ripple
challenges with the same universal engine, swapping case types and
UI skins based on which challenge we ultimately pick.

What's already built and tested:
- FastAPI backend with ~30 endpoints and an ML pipeline
- Next.js dashboard with streaming AI explanations
- 4-jurisdiction rule engine (FINMA/MiCA/SFC/FSRA)
- FINMA-compliant data anonymization
- 18 realistic mock cases across multiple risk levels

Pitch materials are also ready:
- 10-slide deck (Marp format)
- 3-minute demo script with second-by-second timing
- Team onboarding guide
- Code walkthrough for jury Q&A

To get started, please:
1. Clone the repository: <repo URL>
2. Open pitch/team-onboarding.md — it's a 30-minute self-guided setup
3. Run the project locally and confirm it works on your machine

If anything fails, please send me the exact error message — I'd rather
fix any setup issues before the weekend, not during it.

Looking forward to building this with you.

Best,
Stiven
```

---

## Variant D: LinkedIn / public-facing

Если хочешь привлечь внимание к проекту публично — на LinkedIn, Twitter, или для recruiters. **Не** для team announcement.

```
For the past two weeks I've been pre-building a project for SwissHacks
2026 (Tenity, Zurich).

It's a compliance dashboard for FINMA-regulated banks. Built around
three hackathon partner challenges (AMINA, Julius Baer, Ripple) with
the same engine — swap the skin based on which challenge gets picked.

What I built solo before the team joins:
- FastAPI backend, ~30 endpoints, ML pipeline (XGBoost + SHAP + DiCE)
- Next.js 15 dashboard with streaming Claude explanations via SSE
- YAML-driven jurisdiction rule engine (FINMA, MiCA, SFC, FSRA)
- Privacy-by-design anonymizer (FINMA Circular 2024/3 compliant)
- Production touches: error boundaries, retry logic, skeleton states

Stack: Python 3.11, FastAPI, SQLModel, XGBoost, SHAP, DiCE, Anthropic
SDK, Next.js 15, React 19, TypeScript strict, TanStack Query.

Pre-building lets the team focus on the specific challenge details on
the weekend rather than setting up infrastructure. The engine is the
same regardless of which way we go.

Repo: <link>
Demo: localhost:3000 (instructions in README)

Now the team joins, we pick our challenge angle, and we ship.
```

---

## How to use these

Pick **one** variant for the initial announcement. After that:

1. **Pin** the message in the channel so newcomers see it
2. **Edit** with actual repo URL before posting
3. **Follow up** in 24h with a "anyone got it running?" check
4. **Personally DM** anyone who didn't react — silence often means
   "I don't know where to start", not "I'm not interested"

Good luck with the team activation.
