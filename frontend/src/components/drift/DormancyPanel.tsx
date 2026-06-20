"use client";

import { cn, formatCompact, scoreSeverity } from "@/lib/utils";
import type { DormancyVerdict } from "@/types/api";
import { Activity, Moon, Power, X } from "lucide-react";
interface DormancyPanelProps {
  dormancy: DormancyVerdict;
}

/**
 * Dormancy Break panel - the suspicious activation detector.
 *
 * Mirrors Suspicious Stability: two factors are shown separately and then
 * multiplied. The signal only matters when a genuinely dormant baseline is
 * followed by a strong activation burst.
 */
export function DormancyPanel({ dormancy }: DormancyPanelProps) {
  const {
    dormancy_break,
    dormancy_depth,
    activation_strength,
    baseline_volume,
    active_volume,
    is_dormancy_break,
    detail,
  } = dormancy;

  if (dormancy_break < 0.05 && !is_dormancy_break) {
    return null;
  }

  const sev = scoreSeverity(dormancy_break);

  return (
    <div
      className={cn(
        "rounded border border-paper-line p-4",
        is_dormancy_break ? "bg-risk-critical-bg" : "bg-paper-raised",
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <Power
          className={cn(
            "h-3.5 w-3.5",
            is_dormancy_break ? "text-risk-critical" : "text-ink-muted",
          )}
          strokeWidth={2}
        />
        <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Dormancy Break - suspicious activation
        </h3>
        {is_dormancy_break && (
          <span className="text-2xs px-2 py-0.5 rounded font-medium bg-risk-critical text-white">
            FLAGGED
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <FactorBox icon={Moon} label="Dormancy depth" value={dormancy_depth} />
        <X className="h-4 w-4 text-ink-faint shrink-0" strokeWidth={2} />
        <FactorBox
          icon={Activity}
          label="Activation strength"
          value={activation_strength}
        />
        <span className="text-ink-faint font-mono text-sm shrink-0">=</span>
        <div className="text-center shrink-0">
          <div
            className={cn(
              "text-sm font-semibold",
              is_dormancy_break ? "text-risk-critical" : sev.color,
            )}
          >
            {is_dormancy_break ? "Critical" : sev.label}
          </div>
          <div className="text-2xs text-ink-muted font-mono tabular">
            {dormancy_break.toFixed(2)} break score
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 text-2xs text-ink-muted border-t border-paper-line pt-2">
        <span className="min-w-0">
          Baseline volume{" "}
          <span className="font-mono text-ink tabular">
            {formatCompact(baseline_volume)}
          </span>
        </span>
        <span className="min-w-0 text-right">
          Active volume{" "}
          <span className="font-mono text-ink tabular">
            {formatCompact(active_volume)}
          </span>
        </span>
      </div>

      <p
        className={cn(
          "text-2xs mt-2 leading-relaxed",
          is_dormancy_break ? "text-risk-critical font-medium" : "text-ink-faint",
        )}
      >
        {detail}
      </p>
    </div>
  );
}

function FactorBox({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Moon;
  label: string;
  value: number;
}) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex-1 border border-paper-line rounded p-2 bg-paper text-center min-w-0">
      <Icon className="h-3.5 w-3.5 text-accent mx-auto mb-1" strokeWidth={2} />
      <div className="font-mono text-base font-semibold text-ink tabular">{pct}</div>
      <div className="text-2xs text-ink-muted leading-tight">{label}</div>
    </div>
  );
}
