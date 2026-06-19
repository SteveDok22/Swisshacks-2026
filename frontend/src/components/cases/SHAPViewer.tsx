"use client";

import { cn } from "@/lib/utils";
import type { FeatureContribution } from "@/types/api";

interface SHAPViewerProps {
  features: FeatureContribution[];
}

/**
 * Horizontal bar chart of SHAP feature contributions.
 *
 * Design choices:
 * - Custom SVG bars (not Recharts) — full control over typography & color
 * - Risk-increasing → red, risk-decreasing → green (semantic)
 * - Human labels, not raw feature names (no "amount_vs_typical_ratio")
 * - Tabular nums for contribution values
 *
 * This is the "why" of the AI decision, in 5 seconds of scanning.
 */
export function SHAPViewer({ features }: SHAPViewerProps) {
  if (!features || features.length === 0) {
    return (
      <div className="text-sm text-ink-muted">
        No feature contributions available.
      </div>
    );
  }

  // Normalize bar widths to the largest absolute contribution
  const maxAbs = Math.max(...features.map((f) => Math.abs(f.contribution)));

  return (
    <div className="space-y-2.5">
      {features.map((f, i) => {
        const pct = maxAbs > 0 ? (Math.abs(f.contribution) / maxAbs) * 100 : 0;
        const isIncreasing = f.direction === "risk_increasing";
        const sign = f.contribution > 0 ? "+" : "";

        return (
          <div
            key={f.name}
            className="grid grid-cols-[1fr_auto] gap-3 items-center animate-slide-up opacity-0"
            style={{ animationDelay: `${i * 60}ms` }}
          >
            <div>
              <div className="text-xs text-ink leading-snug mb-1">
                {f.human_label ?? f.name}
              </div>
              <div className="h-1.5 bg-paper-sunken rounded-sm overflow-hidden relative">
                <div
                  className={cn(
                    "h-full rounded-sm transition-all duration-700",
                    isIncreasing ? "bg-risk-critical" : "bg-risk-low",
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
            <div
              className={cn(
                "font-mono tabular text-xs font-medium w-14 text-right",
                isIncreasing ? "text-risk-critical" : "text-risk-low",
              )}
            >
              {sign}
              {f.contribution.toFixed(2)}
            </div>
          </div>
        );
      })}

      <div className="flex items-center gap-4 pt-3 mt-3 border-t border-paper-line text-2xs text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-risk-critical" />
          Increases risk
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-risk-low" />
          Decreases risk
        </span>
      </div>
    </div>
  );
}
