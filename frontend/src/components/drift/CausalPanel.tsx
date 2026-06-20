"use client";

import { cn } from "@/lib/utils";
import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { CausalVerdict } from "@/types/api";
import { GitBranch } from "lucide-react";

interface CausalPanelProps {
  causal: CausalVerdict;
}

const METRIC_LABEL: Record<string, string> = {
  volume_change: "Volume",
  margin_change: "Margin",
  counterparty_change: "Counterparty risk",
  corridor_change: "Corridor risk",
};

/**
 * Causal Panel — the differentiator that answers "is this risk or normal life?"
 *
 * Shows the competition between two generative hypotheses (benign business
 * growth vs risk transit) and which metric drove the verdict. The key insight
 * for the jury: drift MAGNITUDE doesn't separate benign from risk — the
 * correlation SIGNATURE does. Margin is the discriminator.
 */
export function CausalPanel({ causal }: CausalPanelProps) {
  const { label, p_risk, causal_llr, contributions } = causal;
  const explanation =
    "Likelihood ratio between two generative hypotheses. Drift magnitude alone cannot separate benign from risk — the correlation signature can.";

  const verdictColor =
    label === "risk"
      ? "text-risk-critical"
      : label === "benign"
        ? "text-risk-low"
        : "text-risk-medium";

  const verdictBg =
    label === "risk"
      ? "bg-risk-critical-bg border-risk-critical/20"
      : label === "benign"
        ? "bg-risk-low-bg border-risk-low/20"
        : "bg-risk-medium-bg border-risk-medium/20";

  // Order contributions by absolute magnitude (most decisive first)
  const ranked = Object.entries(contributions).sort(
    (a, b) => Math.abs(b[1]) - Math.abs(a[1]),
  );

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Causal Analysis"
    >
      <div className="mb-3 flex items-start justify-between gap-3 pr-10">
        <div className="flex items-start gap-2">
          <GitBranch className="h-3.5 w-3.5 text-accent mt-0.5" strokeWidth={2} />
          <div>
            <h3 className="text-sm font-semibold text-ink">Causal Analysis</h3>
            <p className="text-2xs text-ink-muted mt-0.5">
              Risk or normal life?
            </p>
          </div>
        </div>
        <InfoHint text={explanation} />
      </div>

      {/* Verdict banner */}
      <div className={cn("rounded border p-3 mb-3", verdictBg)}>
        <div className="flex items-center justify-between">
          <div>
            <div className={cn("text-sm font-semibold capitalize", verdictColor)}>
              {label === "ambiguous" ? "Ambiguous — needs review" : `${label}-shaped drift`}
            </div>
            <div className="text-2xs text-ink-muted mt-0.5">
              {label === "risk" &&
                "Change matches a transit/laundering signature"}
              {label === "benign" &&
                "Change matches legitimate business growth"}
              {label === "ambiguous" &&
                "Signal insufficient to separate risk from life"}
            </div>
          </div>
          <div className="text-right">
            <div className={cn("font-mono text-xl font-semibold tabular", verdictColor)}>
              {Math.round(p_risk * 100)}%
            </div>
            <div className="text-2xs text-ink-muted">P(risk)</div>
          </div>
        </div>
      </div>

      {/* Two competing hypotheses */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-2xs">
        <div
          className={cn(
            "rounded border p-2 text-center",
            causal_llr < 0 ? "border-risk-low/40 bg-risk-low-bg" : "border-paper-line",
          )}
        >
          <div className="font-medium text-ink">Benign growth</div>
          <div className="text-ink-muted mt-0.5">margin preserved</div>
        </div>
        <div
          className={cn(
            "rounded border p-2 text-center",
            causal_llr > 0 ? "border-risk-critical/40 bg-risk-critical-bg" : "border-paper-line",
          )}
        >
          <div className="font-medium text-ink">Risk transit</div>
          <div className="text-ink-muted mt-0.5">margin collapses</div>
        </div>
      </div>

      {/* Per-metric evidence */}
      <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-2">
        What drove the verdict
      </div>
      <div className="mb-1.5 grid grid-cols-[7rem_1fr_3rem] items-center gap-2 text-[0.625rem] text-ink-faint">
        <span />
        <div className="grid grid-cols-3">
          <span>benign</span>
          <span className="text-center">LLR 0</span>
          <span className="text-right">risk</span>
        </div>
        <span className="text-right">score</span>
      </div>
      <div className="space-y-1.5">
        {ranked.map(([metric, llr]) => {
          const towardRisk = llr > 0;
          const strength = Math.min(Math.abs(llr) / 5, 1);
          return (
            <div key={metric} className="flex items-center gap-2">
              <span className="text-xs text-ink w-28 shrink-0">
                {METRIC_LABEL[metric] ?? metric}
              </span>
              {/* Diverging bar: benign left (green), risk right (red) */}
              <div className="flex-1 flex items-center h-4">
                <div className="flex-1 flex justify-end">
                  {!towardRisk && (
                    <div
                      className="h-2 bg-risk-low rounded-l-sm"
                      style={{ width: `${strength * 100}%` }}
                    />
                  )}
                </div>
                <div className="w-px h-3 bg-ink-faint shrink-0" />
                <div className="flex-1">
                  {towardRisk && (
                    <div
                      className="h-2 bg-risk-critical rounded-r-sm"
                      style={{ width: `${strength * 100}%` }}
                    />
                  )}
                </div>
              </div>
              <span
                className={cn(
                  "font-mono text-2xs tabular w-12 text-right shrink-0",
                  towardRisk ? "text-risk-critical" : "text-risk-low",
                )}
              >
                {llr > 0 ? "+" : ""}
                {llr.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>

    </ZoomablePanel>
  );
}
