"use client";

import { cn, scoreSeverity } from "@/lib/utils";
import type { StabilityVerdict } from "@/types/api";
import { Snowflake, Activity, X } from "lucide-react";

interface StabilityPanelProps {
  stability: StabilityVerdict;
}

/**
 * Suspicious Stability panel — the slow-walker / sleeper detector.
 *
 * Only renders meaningfully when there is something to show. The insight for
 * the jury: this catches the launderer who KNOWS about drift monitoring and
 * stays smooth on purpose. Stability x environmental movement — both factors
 * shown, multiplied.
 */
export function StabilityPanel({ stability }: StabilityPanelProps) {
  const { suspicion, stability_anomaly, environmental_movement, own_volatility, cohort_volatility, is_suspicious, detail } = stability;

  // Only show the panel when there is a real signal (avoid clutter on the
  // majority of calm customers).
  if (suspicion < 0.05 && !is_suspicious) {
    return null;
  }

  const sev = scoreSeverity(suspicion);
  // How calm this customer is versus their peer cohort (the slow-walker tell:
  // unusually low volatility while the cohort moves).
  const volatilityRatio =
    cohort_volatility > 0 ? own_volatility / cohort_volatility : null;

  return (
    <div
      className={cn(
        "rounded border border-paper-line p-4",
        is_suspicious ? "bg-risk-high-bg" : "bg-paper-raised",
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <Snowflake
          className={cn("h-3.5 w-3.5", is_suspicious ? "text-risk-high" : "text-ink-muted")}
          strokeWidth={2}
        />
        <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Suspicious Stability — the slow-walker check
        </h3>
        {is_suspicious && (
          <span className="text-2xs px-2 py-0.5 rounded font-medium bg-risk-high text-white">
            FLAGGED
          </span>
        )}
      </div>

      {/* The product equation, shown visually */}
      <div className="flex items-center gap-2 mb-3">
        <FactorBox
          icon={Snowflake}
          label="Unnatural smoothness"
          value={stability_anomaly}
        />
        <X className="h-4 w-4 text-ink-faint shrink-0" strokeWidth={2} />
        <FactorBox
          icon={Activity}
          label="Environment moving"
          value={environmental_movement}
        />
        <span className="text-ink-faint font-mono text-sm shrink-0">=</span>
        <div className="text-center shrink-0">
          <div
            className={cn(
              "text-sm font-semibold",
              is_suspicious ? "text-risk-high" : sev.color,
            )}
          >
            {is_suspicious ? "High" : sev.label}
          </div>
          <div className="text-2xs text-ink-muted font-mono tabular">
            {suspicion.toFixed(2)} suspicion
          </div>
        </div>
      </div>

      {/* Volatility comparison */}
      <div className="flex items-center justify-between text-2xs text-ink-muted border-t border-paper-line pt-2">
        <span>Movement vs peer cohort</span>
        {volatilityRatio !== null ? (
          <span className="text-ink">
            <span className="font-mono tabular">{volatilityRatio.toFixed(1)}×</span>{" "}
            cohort norm{" "}
            <span className="text-ink-muted">
              ({volatilityRatio < 0.8 ? "calmer than peers" : volatilityRatio > 1.2 ? "more volatile" : "in line"})
            </span>
          </span>
        ) : (
          <span className="text-ink-muted">n/a</span>
        )}
      </div>

      <p
        className={cn(
          "text-2xs mt-2 leading-relaxed",
          is_suspicious ? "text-risk-high font-medium" : "text-ink-faint",
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
  icon: typeof Snowflake;
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
