"use client";

import Link from "next/link";
import {
  ArrowRight,
  Shield,
  Layers,
  Activity,
  Lock,
  GitBranch,
  Scale,
  Sparkles,
  Github,
} from "lucide-react";

/**
 * About / Welcome page.
 *
 * First thing a new team member sees when they fork the repo.
 * Also serves as a "what is this product" reference during demo.
 *
 * Tone: Swiss-institutional, factual, no marketing fluff.
 */
export default function AboutPage() {
  return (
    <div className="min-h-screen bg-paper relative z-10">
      {/* Top bar */}
      <header className="border-b border-paper-line bg-paper-raised">
        <div className="max-w-5xl mx-auto px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded bg-accent flex items-center justify-center">
              <span className="text-paper-raised font-semibold text-sm">S</span>
            </div>
            <div className="leading-tight">
              <div className="font-semibold text-sm text-ink">Sentinel</div>
              <div className="text-2xs text-ink-muted">Risk Intelligence</div>
            </div>
          </Link>
          <Link
            href="/"
            className="text-xs font-medium text-accent hover:text-accent-soft flex items-center gap-1"
          >
            Open dashboard
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-8 py-12">
        {/* Hero */}
        <section className="mb-16 max-w-3xl">
          <div className="text-2xs font-semibold uppercase tracking-wide text-accent mb-3">
            SwissHacks 2026 · Risk Intelligence Platform
          </div>
          <h1 className="text-3xl font-semibold text-ink leading-tight mb-4 tracking-tight">
            Explainable AI for compliance officers in regulated banks.
          </h1>
          <p className="text-base text-ink-soft leading-relaxed">
            Sentinel adapts a universal risk engine to multiple challenges —
            social engineering attacks, investment recommendations, on-chain
            transactions, client onboarding — all with the same explainable
            backbone: SHAP analysis, counterfactual reasoning, and
            jurisdiction-specific rule packs.
          </p>
        </section>

        {/* Differentiators */}
        <section className="mb-16">
          <h2 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-6">
            What makes this different
          </h2>
          <div className="grid grid-cols-2 gap-5">
            <Differentiator
              icon={Lock}
              title="Local-first AI"
              body="Critical client data never leaves the bank. Names become pseudonyms, exact amounts become buckets. Only anonymized features reach the LLM — auditable, FINMA-compliant by design."
            />
            <Differentiator
              icon={GitBranch}
              title="Counterfactual reasoning"
              body="Beyond SHAP, we use Microsoft Research's DiCE to answer the question compliance officers actually ask: what would need to change for this to be approved?"
            />
            <Differentiator
              icon={Scale}
              title="Jurisdiction rule packs"
              body="Same case, four regulators. FINMA, MiCA, SFC, FSRA each have YAML-defined thresholds, modifiers, and reporting requirements. Toggle the jurisdiction, watch the action change."
            />
            <Differentiator
              icon={Sparkles}
              title="Streaming AI narrative"
              body="Server-Sent Events stream Claude's analysis progressively. The officer reads the reasoning as it's generated — not a wall of pre-computed text."
            />
          </div>
        </section>

        {/* Architecture */}
        <section className="mb-16">
          <h2 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-6">
            Architecture
          </h2>
          <div className="border border-paper-line rounded p-6 bg-paper-raised">
            <pre className="font-mono text-2xs text-ink-soft leading-relaxed overflow-x-auto">
{`Case  →  RiskEngine  →  SHAP        →  Anonymizer  →  Claude  →  Narrative
              ↓                                            ↓
        Counterfactuals                              Jurisdiction
        (DiCE)                                       Rule Pack
              ↓                                            ↓
                          Decision (Allow / Escalate / Block)
                                       ↓
                          Append-only Audit Log (SQLite)`}
            </pre>
          </div>
        </section>

        {/* For teammates */}
        <section className="mb-16">
          <h2 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-6">
            For team members joining the project
          </h2>
          <div className="space-y-3">
            <TeammateStep
              n="1"
              title="Read the day-by-day guides"
              body="BUILD_JOURNAL.md walks through every architectural decision, day by day. Skim it in order to understand why things are built this way."
            />
            <TeammateStep
              n="2"
              title="Run it locally"
              body={
                <>
                  <code className="font-mono text-2xs bg-paper-sunken px-1.5 py-0.5 rounded">
                    backend
                  </code>
                  : <code className="font-mono text-2xs bg-paper-sunken px-1.5 py-0.5 rounded">
                    uvicorn app.main:app --reload
                  </code>{" "}
                  ·{" "}
                  <code className="font-mono text-2xs bg-paper-sunken px-1.5 py-0.5 rounded">
                    frontend
                  </code>
                  : <code className="font-mono text-2xs bg-paper-sunken px-1.5 py-0.5 rounded">
                    npm install &amp;&amp; npm run dev
                  </code>
                </>
              }
            />
            <TeammateStep
              n="3"
              title="Explore the API"
              body={
                <>
                  19 endpoints documented at{" "}
                  <code className="font-mono text-2xs bg-paper-sunken px-1.5 py-0.5 rounded">
                    localhost:8000/docs
                  </code>
                  . Each one auto-generated from Pydantic schemas.
                </>
              }
            />
            <TeammateStep
              n="4"
              title="Pick an area to deepen"
              body="Voice deepfake detection (AMINA), Julius Baer skin, Ripple XRPL integration, behavioral baselines, more sophisticated mock data — pick what excites you, the architecture supports it."
            />
          </div>
        </section>

        {/* Tech stack */}
        <section className="mb-16">
          <h2 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-6">
            Stack
          </h2>
          <div className="grid grid-cols-3 gap-3 text-2xs">
            <StackBlock
              label="Backend"
              items={[
                "FastAPI · Pydantic",
                "SQLite + SQLModel (async)",
                "XGBoost + SHAP",
                "DiCE counterfactuals",
                "Anthropic Claude SDK",
                "sse-starlette streaming",
                "structlog · uv",
              ]}
            />
            <StackBlock
              label="Frontend"
              items={[
                "Next.js 15 · React 19",
                "TypeScript strict",
                "Tailwind v3",
                "TanStack Query",
                "Radix UI primitives",
                "Geist + IBM Plex Mono",
                "Lucide icons",
              ]}
            />
            <StackBlock
              label="Infra"
              items={[
                "Docker Compose",
                "uv (Python deps)",
                "npm (frontend)",
                "Git",
                "Server-Sent Events",
                "Mock mode (no API key)",
              ]}
            />
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-paper-line pt-6 mt-12 flex items-center justify-between text-2xs text-ink-muted">
          <div>Built for SwissHacks 2026 · Zürich</div>
          <Link
            href="/"
            className="flex items-center gap-1.5 hover:text-ink transition-colors"
          >
            <Activity className="h-3 w-3" strokeWidth={2} />
            Open Sentinel dashboard
          </Link>
        </footer>
      </main>
    </div>
  );
}

function Differentiator({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Shield;
  title: string;
  body: string;
}) {
  return (
    <div className="border border-paper-line rounded p-5 bg-paper-raised">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-3.5 w-3.5 text-accent" strokeWidth={2} />
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
      </div>
      <p className="text-xs text-ink-soft leading-relaxed">{body}</p>
    </div>
  );
}

function TeammateStep({
  n,
  title,
  body,
}: {
  n: string;
  title: string;
  body: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-4 border border-paper-line rounded p-4 bg-paper-raised">
      <div className="h-6 w-6 shrink-0 rounded bg-accent-bg flex items-center justify-center font-mono text-2xs font-semibold text-accent">
        {n}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-ink mb-0.5">{title}</div>
        <div className="text-xs text-ink-soft leading-relaxed">{body}</div>
      </div>
    </div>
  );
}

function StackBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="border border-paper-line rounded p-4 bg-paper-raised">
      <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-2.5">
        {label}
      </div>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item} className="text-2xs text-ink-soft font-mono">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
