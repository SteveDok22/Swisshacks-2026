"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import {
  X,
  Sparkles,
  Shield,
  GitBranch,
  Scale,
  ArrowRight,
} from "lucide-react";

const STORAGE_KEY = "sentinel.welcome-seen";

/**
 * One-time welcome modal explaining the product on first visit.
 *
 * Shown automatically the first time a user opens the dashboard.
 * Stored in localStorage so it doesn't show every refresh.
 * Can be reopened from the sidebar (future).
 */
export function WelcomeModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Only show if user has never seen it
    try {
      const seen = localStorage.getItem(STORAGE_KEY);
      if (!seen) {
        // Small delay so the page renders first
        const t = setTimeout(() => setOpen(true), 400);
        return () => clearTimeout(t);
      }
    } catch {
      // SSR or storage disabled — skip
    }
  }, []);

  // Esc to close — important for demo: if it accidentally opens mid-pitch,
  // you can dismiss it without clicking the (small) X button
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const dismiss = () => {
    setOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // Ignore
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm animate-fade-in p-6"
      onClick={dismiss}
    >
      <div
        className="bg-paper-raised border border-paper-line rounded shadow-raised max-w-2xl w-full overflow-hidden animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-7 pt-6 pb-5 border-b border-paper-line">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded bg-accent flex items-center justify-center">
                <span className="text-paper-raised font-semibold text-base">
                  S
                </span>
              </div>
              <div>
                <h1 className="text-base font-semibold text-ink">
                  Welcome to Sentinel
                </h1>
                <p className="text-xs text-ink-muted mt-0.5">
                  Risk Intelligence Platform · SwissHacks 2026
                </p>
              </div>
            </div>
            <button
              onClick={dismiss}
              className="text-ink-muted hover:text-ink p-1"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <p className="text-sm text-ink-soft leading-relaxed">
            Explainable AI for compliance officers in FINMA-regulated banks.
            Score cases, understand the reasoning, and decide — all with
            full audit trail.
          </p>
        </div>

        {/* Differentiators grid */}
        <div className="px-7 py-5">
          <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-3">
            What makes this different
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Feature
              icon={Sparkles}
              title="Streaming AI"
              desc="Live natural-language explanations powered by Claude. Words appear as the model reasons."
            />
            <Feature
              icon={GitBranch}
              title="Counterfactuals"
              desc="DiCE-powered 'what would change this decision' scenarios. Beyond static SHAP."
            />
            <Feature
              icon={Shield}
              title="Privacy by design"
              desc="Client identifiers and amounts are anonymized before any LLM call. FINMA-compliant."
            />
            <Feature
              icon={Scale}
              title="Jurisdiction-aware"
              desc="Same case scored under FINMA, MiCA, SFC, or FSRA rule packs. Live toggle."
            />
          </div>
        </div>

        {/* Suggested flow */}
        <div className="px-7 py-5 bg-paper-sunken border-t border-paper-line">
          <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-2.5">
            Try this demo flow (3 minutes)
          </div>
          <ol className="space-y-1.5 text-xs text-ink-soft">
            <li>
              <span className="font-mono text-ink-muted">1.</span> Open the
              <span className="font-medium text-ink"> Marc Weber</span> case
              (highest risk in queue)
            </li>
            <li>
              <span className="font-mono text-ink-muted">2.</span> Watch the AI
              assessment stream in
            </li>
            <li>
              <span className="font-mono text-ink-muted">3.</span> Review SHAP
              factors and alternative scenarios
            </li>
            <li>
              <span className="font-mono text-ink-muted">4.</span> Toggle the
              jurisdiction (try AE/FSRA — strictest)
            </li>
            <li>
              <span className="font-mono text-ink-muted">5.</span> Expand the
              Data Handling panel to see what goes to AI
            </li>
            <li>
              <span className="font-mono text-ink-muted">6.</span> Record your
              decision — Block, or override with rationale
            </li>
          </ol>
        </div>

        {/* Footer */}
        <div className="px-7 py-4 border-t border-paper-line flex items-center justify-between">
          <span className="text-2xs text-ink-muted">
            Backend on :8000 · Frontend on :3000
          </span>
          <button
            onClick={dismiss}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-accent text-paper-raised text-xs font-medium hover:bg-accent-soft transition-colors"
          >
            Open the queue
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </div>
  );
}

function Feature({
  icon: Icon,
  title,
  desc,
}: {
  icon: typeof Sparkles;
  title: string;
  desc: string;
}) {
  return (
    <div className="border border-paper-line rounded p-3 bg-paper-raised">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon
          className="h-3.5 w-3.5 text-accent"
          strokeWidth={2}
        />
        <span className="text-xs font-semibold text-ink">{title}</span>
      </div>
      <p className="text-2xs text-ink-muted leading-relaxed">{desc}</p>
    </div>
  );
}
