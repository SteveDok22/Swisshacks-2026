"use client";

import Link from "next/link";
import Image from "next/image";
import {
  ArrowRight,
  Activity,
  Zap,
  GitBranch,
  Snowflake,
  Clock,
  Network,
  Globe,
  DollarSign,
  ShieldCheck,
} from "lucide-react";

/**
 * About / Welcome page — Sentinel Drift Engine.
 *
 * First thing a teammate or judge sees. Swiss-institutional base (it is a
 * bank compliance tool), lifted with a hero, feature cards, and the
 * architecture diagram. AMINA teal accent throughout.
 */
export default function AboutPage() {
  return (
    <div className="min-h-screen bg-paper relative z-10">
      {/* Top bar */}
      <header className="border-b border-paper-line bg-paper-raised/90 backdrop-blur sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <Image
              src="/assets/logo.png"
              alt="Sentinel logo"
              width={28}
              height={28}
              className="h-7 w-7 rounded object-contain"
              priority
            />
            <div className="leading-tight">
              <div className="font-serif font-semibold text-base text-ink tracking-tight">Sentinel</div>
              <div className="text-2xs text-ink-muted">Risk Intelligence</div>
            </div>
          </Link>
          <Link
            href="/drift"
            className="text-xs font-medium text-accent hover:text-accent-soft flex items-center gap-1"
          >
            Open Drift Engine
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
          </Link>
        </div>
      </header>

      {/* ===== HERO ===== */}
      <section className="relative overflow-hidden border-b border-paper-line">
        {/* soft teal wash backdrop */}
        <div
          className="absolute inset-0 -z-0"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 20% 0%, #e8f1f3 0%, rgba(232,241,243,0) 60%), radial-gradient(ellipse 60% 50% at 100% 100%, #f0fdf4 0%, rgba(240,253,244,0) 55%)",
          }}
        />
        <div className="relative max-w-6xl mx-auto px-8 py-20">
          <HeroVisual className="pointer-events-none absolute right-0 top-10 hidden h-[360px] w-[440px] opacity-90 xl:block" />
          <h1 className="text-4xl sm:text-5xl font-semibold text-ink leading-[1.08] tracking-tight max-w-3xl">
            Catch KYC drift{" "}
            <span className="text-accent">before</span> it becomes a sanctions hit.
          </h1>
          <p className="mt-6 text-lg text-ink-soft leading-relaxed max-w-2xl">
            Sentinel detects the slow structural changes that quietly invalidate a
            customer&apos;s original risk profile — combining real-time public
            signals with internal bank data, months ahead of any watchlist.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/drift"
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-white hover:bg-accent-soft transition-colors"
            >
              Open the Drift Engine
              <ArrowRight className="h-4 w-4" strokeWidth={2.5} />
            </Link>
            <a
              href="#architecture"
              className="inline-flex items-center gap-2 rounded-lg border border-paper-line bg-paper-raised px-5 py-3 text-sm font-semibold text-ink-soft hover:text-ink hover:border-accent/30 transition-colors"
            >
              See the architecture
            </a>
          </div>

          {/* Stat strip */}
          <div className="mt-14 grid grid-cols-2 sm:grid-cols-4 gap-px rounded-xl overflow-hidden border border-paper-line bg-paper-line">
            <Stat value="2–7 mo" label="Lead time vs sanctions" />
            <Stat value="96%" label="Cheaper than LLM-on-all" />
            <Stat value="0" label="False positives on stable" />
            <Stat value="8" label="Detection layers" />
          </div>
        </div>
      </section>

      <main className="max-w-6xl mx-auto px-8 py-16">
        {/* ===== THE PROBLEM ===== */}
        <section className="mb-20 max-w-3xl">
          <SectionLabel>The problem</SectionLabel>
          <p className="text-xl text-ink leading-relaxed font-light">
            A customer is onboarded as low-risk. Two years later their company
            has taken money from a sanctioned entity, their counterparties have
            shifted to high-risk corridors, and their volume has tripled — but{" "}
            <span className="font-medium text-accent">gradually</span>. No single
            event tripped an alert. The original KYC profile is now invalid, and
            nobody noticed.
          </p>
        </section>

        {/* ===== HOW IT WORKS (feature cards) ===== */}
        <section className="mb-20">
          <SectionLabel>How it works</SectionLabel>
          <p className="text-ink-soft mb-8 max-w-2xl">
            Eight layers fuse into a single drift score. The first four read the
            signal; the last three are what no other team will have.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <FeatureCard
              icon={Activity}
              kicker="Layer 1"
              title="Behavioral Drift"
              body="Bayesian Online Changepoint Detection catches a regime change the moment the process shifts — even slow creep that never trips a threshold."
            />
            <FeatureCard
              icon={Zap}
              kicker="Layer 2"
              title="Drift Velocity"
              body="The time-derivative of KL divergence from the onboarding profile. Rising velocity is the earliest precursor — it leads the drift level."
            />
            <FeatureCard
              icon={Network}
              kicker="Layer 3"
              title="Ownership Contagion"
              body="Personalized PageRank propagates risk from a sanctioned entity through ownership links to customers on no watchlist themselves."
            />
            <FeatureCard
              icon={Globe}
              kicker="Layer 4"
              title="Public Intelligence + Lift"
              body="Public signals fused with internal drift. Confirmation Lift measures how much an external story and internal behavior, co-occurring in time, reinforce each other."
            />
            <FeatureCard
              icon={GitBranch}
              kicker="Differentiator"
              title="Causal Drift"
              body="A likelihood ratio between two hypotheses separates risk-shaped change from legitimate business growth. Same velocity, opposite verdict."
              accent
            />
            <FeatureCard
              icon={Snowflake}
              kicker="Differentiator"
              title="Suspicious Stability"
              body="Flags the slow-walker: a customer anomalously smooth while their environment moves — the launderer who knows drift is monitored and stays still."
              accent
            />
            <FeatureCard
              icon={Clock}
              kicker="Differentiator"
              title="Time-Travel Audit"
              body="Replays any customer as-of any past month using only data available then — proving early detection with no look-ahead bias. Regulator-grade."
              accent
            />
            <FeatureCard
              icon={DollarSign}
              kicker="Cost control"
              title="Cost-Aware Cascade"
              body="Cheap rules filter first, ML next, LLM reasoning only where it pays off. 96% cheaper than running the model on everyone."
            />
            <FeatureCard
              icon={ShieldCheck}
              kicker="Guardrails"
              title="Explain · HITL · Audit"
              body="Per-layer breakdown on every score, a verdict bar with the recommended action, officer override with rationale, and an immutable audit log."
            />
          </div>
        </section>

        {/* ===== ARCHITECTURE ===== */}
        <section id="architecture" className="mb-20 scroll-mt-20">
          <SectionLabel>Architecture</SectionLabel>
          <p className="text-ink-soft mb-6 max-w-2xl">
            The Drift Engine sits at the center; the rest of the platform —
            scoring, privacy, jurisdiction packs, the officer decision flow —
            wraps around it.
          </p>
          <div className="rounded-xl border border-paper-line bg-paper-raised p-3 sm:p-5 overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/sentinel-architecture.png"
              alt="Sentinel Drift Engine architecture diagram"
              className="w-full h-auto rounded-lg"
            />
          </div>
        </section>

        {/* ===== FOR TEAMMATES ===== */}
        <section className="mb-20">
          <SectionLabel>For team members joining the project</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <TeammateStep
              n="1"
              title="Read the technical spec"
              body="DRIFT_ENGINE_README.md explains the approach, the math behind each layer, and the academic references."
            />
            <TeammateStep
              n="2"
              title="Run it locally"
              body={
                <>
                  <Code>uvicorn app.main:app --reload</Code> ·{" "}
                  <Code>npm install &amp;&amp; npm run dev</Code>
                </>
              }
            />
            <TeammateStep
              n="3"
              title="Explore the API"
              body={
                <>
                  33 endpoints at <Code>localhost:8000/docs</Code>, auto-generated
                  from Pydantic schemas.
                </>
              }
            />
            <TeammateStep
              n="4"
              title="Pick an area to deepen"
              body="Real public-signal feeds, richer ownership graphs, more drift scenarios, conformal prediction — the architecture supports it."
            />
          </div>
        </section>

        {/* ===== STACK ===== */}
        <section className="mb-16">
          <SectionLabel>Stack</SectionLabel>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-2xs">
            <StackBlock
              label="Backend"
              items={[
                "FastAPI · Pydantic v2",
                "SQLModel + SQLite (async)",
                "NumPy · SciPy (BOCPD, KL)",
                "NetworkX (PageRank)",
                "XGBoost · SHAP · DiCE",
                "Anthropic Claude SDK",
                "SSE streaming · structlog",
              ]}
            />
            <StackBlock
              label="Frontend"
              items={[
                "Next.js 15 · React 19",
                "TypeScript strict",
                "Tailwind v3 · AMINA teal",
                "TanStack Query",
                "Radix UI primitives",
                "Bitter + Satoshi + IBM Plex Mono",
                "Lucide icons",
              ]}
            />
            <StackBlock
              label="Infra"
              items={[
                "Docker Compose",
                "33 endpoints · 4 rule packs",
                "8 drift modules",
                "Mock mode (no API key)",
                "All data synthetic",
                "Git · GitHub",
              ]}
            />
          </div>
        </section>

        {/* ===== TEAM ===== */}
        <section className="mt-16">
          <SectionLabel>Team</SectionLabel>
          <div className="rounded-xl border border-paper-line bg-paper-raised p-6">
            <div className="flex items-baseline gap-2 mb-5">
              <h3 className="font-serif text-xl font-semibold text-ink tracking-tight">
                OSNOVA
              </h3>
              <span className="text-2xs text-ink-muted">the team behind Sentinel</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                "Danylo Serhieiev",
                "Danylo Halytskyi",
                "Stiven Ntoktorov",
                "Mykola Tsaryk",
                "Pavlo Bohulov",
              ].map((name) => (
                <div key={name} className="flex items-center gap-2.5">
                  <span className="h-8 w-8 rounded-full bg-accent-bg text-accent flex items-center justify-center text-2xs font-semibold shrink-0">
                    {name
                      .split(" ")
                      .map((w) => w[0])
                      .join("")}
                  </span>
                  <span className="text-sm text-ink">{name}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-paper-line pt-6 mt-12 flex items-center justify-between text-2xs text-ink-muted">
          <div>Sentinel · Built by team OSNOVA · SwissHacks 2026 · Zürich</div>
          <Link
            href="/drift"
            className="flex items-center gap-1.5 hover:text-accent transition-colors"
          >
            <Activity className="h-3 w-3" strokeWidth={2} />
            Open Drift Engine
          </Link>
        </footer>
      </main>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-2xs font-semibold uppercase tracking-wide text-accent mb-4 flex items-center gap-2">
      <span className="h-px w-6 bg-accent/40" />
      {children}
    </h2>
  );
}

/**
 * Minimalist animated hero visual — the product thesis as a vector:
 * a drift trajectory rising across the alert threshold, a scanner sweeping
 * the curve, radar rings pulsing at the detection point, and a muted red
 * sanctions node it would have reached later. Pure SMIL, no libraries.
 */
function HeroVisual({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 440 380" className={className} fill="none" aria-hidden="true">
      <g>
        {/* whole scene breathes gently */}
        <animateTransform
          attributeName="transform"
          type="translate"
          values="0 0;0 -10;0 0"
          dur="7s"
          repeatCount="indefinite"
          calcMode="spline"
          keyTimes="0;0.5;1"
          keySplines="0.45 0 0.55 1;0.45 0 0.55 1"
        />

        {/* baseline + alert threshold */}
        <line x1="30" y1="330" x2="410" y2="330" stroke="var(--paper-line,#e5e7eb)" strokeWidth="1" />
        <line x1="30" y1="230" x2="410" y2="230" stroke="var(--ink-faint,#9ca3af)" strokeWidth="1.5" strokeDasharray="5 6" />
        <text x="34" y="222" fontSize="11" fill="var(--ink-muted,#6b7280)">alert threshold</text>

        {/* drift trajectory */}
        <path
          id="driftPath"
          d="M30 330 C 110 322, 150 300, 212 230 S 330 92, 410 64"
          stroke="var(--accent,#0d9488)"
          strokeWidth="3"
          strokeLinecap="round"
        />

        {/* scanner dot sweeping along the curve */}
        <circle r="5" fill="var(--accent,#0d9488)">
          <animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.85;1" calcMode="linear">
            <mpath href="#driftPath" />
          </animateMotion>
          <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.06;0.85;1" dur="6s" repeatCount="indefinite" />
        </circle>

        {/* detection node + expanding radar rings at the crossing */}
        <circle cx="212" cy="230" r="6" fill="var(--accent,#0d9488)" />
        <circle cx="212" cy="230" r="6" fill="none" stroke="var(--accent,#0d9488)" strokeWidth="2">
          <animate attributeName="r" values="6;40" dur="3.2s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.55;0" dur="3.2s" repeatCount="indefinite" />
        </circle>
        <circle cx="212" cy="230" r="6" fill="none" stroke="var(--accent,#0d9488)" strokeWidth="2">
          <animate attributeName="r" values="6;40" dur="3.2s" begin="1.6s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.55;0" dur="3.2s" begin="1.6s" repeatCount="indefinite" />
        </circle>

        {/* sanctions node it would have reached later — caught early */}
        <circle cx="410" cy="64" r="5" fill="var(--risk-critical,#b91c1c)" opacity="0.45">
          <animate attributeName="opacity" values="0.25;0.55;0.25" dur="3s" repeatCount="indefinite" />
        </circle>

        {/* faint floating data points */}
        <circle cx="95" cy="312" r="2.5" fill="var(--ink-faint,#9ca3af)">
          <animate attributeName="cy" values="312;304;312" dur="5s" repeatCount="indefinite" />
        </circle>
        <circle cx="150" cy="292" r="2" fill="var(--ink-faint,#9ca3af)">
          <animate attributeName="cy" values="292;300;292" dur="6.5s" repeatCount="indefinite" />
        </circle>
        <circle cx="322" cy="150" r="2.5" fill="var(--ink-faint,#9ca3af)">
          <animate attributeName="cy" values="150;142;150" dur="5.5s" repeatCount="indefinite" />
        </circle>
      </g>
    </svg>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-paper-raised px-5 py-5">
      <div className="font-mono text-2xl font-semibold text-accent tabular-nums">
        {value}
      </div>
      <div className="text-2xs text-ink-muted mt-1 leading-tight">{label}</div>
    </div>
  );
}

function FeatureCard({
  icon: Icon,
  kicker,
  title,
  body,
  accent = false,
}: {
  icon: typeof Activity;
  kicker: string;
  title: string;
  body: string;
  accent?: boolean;
}) {
  return (
    <div
      className={
        "rounded-xl border p-5 transition-colors " +
        (accent
          ? "border-accent/30 bg-accent-bg/40 hover:border-accent/50"
          : "border-paper-line bg-paper-raised hover:border-accent/25")
      }
    >
      <div className="flex items-center gap-2.5 mb-2.5">
        <div
          className={
            "h-8 w-8 rounded-lg flex items-center justify-center shrink-0 " +
            (accent ? "bg-accent text-white" : "bg-accent-bg text-accent")
          }
        >
          <Icon className="h-4 w-4" strokeWidth={2} />
        </div>
        <div>
          <div className="text-2xs font-semibold uppercase tracking-wide text-ink-faint">
            {kicker}
          </div>
          <h3 className="text-sm font-semibold text-ink leading-tight">{title}</h3>
        </div>
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
    <div className="flex items-start gap-4 border border-paper-line rounded-xl p-4 bg-paper-raised">
      <div className="h-7 w-7 shrink-0 rounded-lg bg-accent flex items-center justify-center font-mono text-xs font-semibold text-white">
        {n}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-ink mb-0.5">{title}</div>
        <div className="text-xs text-ink-soft leading-relaxed">{body}</div>
      </div>
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-2xs bg-paper-sunken px-1.5 py-0.5 rounded text-ink-soft">
      {children}
    </code>
  );
}

function StackBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="border border-paper-line rounded-xl p-4 bg-paper-raised">
      <div className="text-2xs font-semibold uppercase tracking-wide text-accent mb-2.5">
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
