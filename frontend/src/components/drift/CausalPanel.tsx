"use client";

import { cn } from "@/lib/utils";
import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { CausalVerdict } from "@/types/api";
import { GitBranch, TrendingUp } from "lucide-react";

interface CausalPanelProps {
  causal: CausalVerdict;
}

const METRIC_LABEL: Record<string, string> = {
  volume_change: "Volume",
  margin_change: "Margin",
  counterparty_change: "Counterparty risk",
  corridor_change: "Corridor risk",
};

// The scale-jump × funding corroboration (UC6) is not a per-metric movement —
// it is a fixed positive boost added when a >=5x active/baseline volume jump is
// confirmed by a public funding_event in the same window. Render it separately
// from the diverging per-metric bars so the corroboration reads as explicit
// evidence, not as one more metric.
const SCALE_JUMP_FUNDING = "scale_jump_funding";

/**
 * Causal Panel — the differentiator that answers "is this risk or normal life?"
 *
 * Shows the competition between two generative hypotheses (benign business
 * growth vs risk transit) and which metric drove the verdict. The key insight
 * for the jury: drift MAGNITUDE doesn't separate benign from risk — the
 * correlation SIGNATURE does. Margin is the discriminator.
 */
export function CausalPanel({ causal }: CausalPanelProps) {
  const { causal_llr, contributions } = causal;
  const explanation =
    "Likelihood ratio between two generative hypotheses. Drift magnitude alone cannot separate benign from risk — the correlation signature can.";

  // Pull the scale-jump × funding corroboration out of the per-metric ranking —
  // it gets its own callout below the metric bars (UC6).
  const scaleJumpFunding = contributions[SCALE_JUMP_FUNDING];
  // Order the remaining per-metric contributions by absolute magnitude (most
  // decisive first).
  const ranked = Object.entries(contributions)
    .filter(([metric]) => metric !== SCALE_JUMP_FUNDING)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));

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

      {/* Two competing hypotheses */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-2xs">
        <div
          className={cn(
            "rounded border border-paper-line p-2 text-center",
            causal_llr < 0 && "bg-risk-low-bg",
          )}
        >
          <div className="font-medium text-ink">Benign growth</div>
          <div className="text-ink-muted mt-0.5">margin preserved</div>
        </div>
        <div
          className={cn(
            "rounded border border-paper-line p-2 text-center",
            causal_llr > 0 && "bg-risk-critical-bg",
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
          <span className="text-center">neutral</span>
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

      {/* Scale-jump × funding corroboration (UC6): a >=5x volume jump confirmed
          by a public funding event in the same window — a scale risk in its own
          right (the FTX pattern). */}
      {scaleJumpFunding !== undefined && (
        <div className="flex items-center gap-2 rounded border border-risk-critical/20 bg-risk-critical-bg py-2 px-2.5 mt-3">
          <TrendingUp className="h-3.5 w-3.5 shrink-0 text-risk-critical" strokeWidth={2} />
          <span className="text-xs font-medium text-risk-critical">
            Scale-jump corroborated by funding event
          </span>
          <span className="text-2xs text-ink-muted">
            — ≥5x volume jump confirmed in the same window
          </span>
          <span className="ml-auto font-mono text-2xs tabular text-risk-critical shrink-0">
            +{scaleJumpFunding.toFixed(1)}
          </span>
        </div>
      )}
    </ZoomablePanel>
  );
}
