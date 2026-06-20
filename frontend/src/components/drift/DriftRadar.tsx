"use client";

import { cn } from "@/lib/utils";
import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { DriftCustomerSummary } from "@/types/api";

interface DriftRadarProps {
  customers: DriftCustomerSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/**
 * Drift Radar — a scatter plot positioning every customer by
 * drift score (x) and drift velocity (y).
 *
 * The upper-right quadrant ("rising and already high") is where the
 * compliance officer's morning begins. This single view replaces a
 * spreadsheet of hundreds of rows.
 *
 * Custom SVG (not a chart library) — full control over the quadrant
 * shading, axis labels, and our design tokens.
 */
export function DriftRadar({ customers, selectedId, onSelect }: DriftRadarProps) {
  const W = 520;
  const H = 380;
  const PAD_X = 68;
  const PAD_Y = 44;
  const explanation =
    "Current book snapshot. X-axis is fused drift score (0–100); Y-axis is drift velocity in bits per month on a log scale — this keeps dormancy-break outliers visible without collapsing the rest. Higher and farther right = most urgent.";

  const maxScore = 100;

  // Log scale for velocity: KL divergence ranges from ~0 (stable) to 5000+
  // (dormancy break). A linear axis collapses everything to the floor when one
  // outlier dominates. log(1 + v) gives every entity meaningful vertical spread.
  const logV = (v: number) => Math.log1p(Math.max(0, v));
  const maxLogVel = Math.max(logV(1), ...customers.map((c) => logV(c.drift_velocity)));

  const sx = (score: number) =>
    PAD_X + (score / maxScore) * (W - PAD_X - PAD_Y);
  const sy = (vel: number) =>
    H - PAD_Y - (logV(vel) / maxLogVel) * (H - 2 * PAD_Y);

  const scoreTicks = [0, 25, 50, 75, 100];
  // Pick 3 human-readable velocity tick values on the original scale
  const rawMax = Math.max(1, ...customers.map((c) => c.drift_velocity));
  const velTickValues = [0, Math.sqrt(rawMax), rawMax].map((v) => Math.round(v));
  const formatVelocityTick = (tick: number) => {
    if (tick >= 1000) return `${(tick / 1000).toFixed(1)}k`;
    return tick.toFixed(0);
  };

  const dotColor = (band: string) => {
    switch (band) {
      case "rapid":
        return "var(--risk-critical, #b91c1c)";
      case "structural":
        return "var(--risk-high, #c2410c)";
      case "notable":
        return "var(--risk-medium, #a16207)";
      default:
        return "var(--risk-low, #15803d)";
    }
  };

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Drift Radar"
    >
      <div className="flex items-center justify-between gap-3 mb-3 pr-10">
        <div>
          <h3 className="text-sm font-semibold text-ink">Drift Radar</h3>
        </div>
        <div className="flex items-center gap-3 text-2xs text-ink-muted">
          <InfoHint text={explanation} />
          {["natural", "notable", "structural", "rapid"].map((b) => (
            <span key={b} className="flex items-center gap-1">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: dotColor(b) }}
              />
              {b}
            </span>
          ))}
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Quadrant shading: upper-right danger zone */}
        <rect
          x={sx(55)}
          y={PAD_Y}
          width={W - PAD_Y - sx(55)}
          height={sy(rawMax * 0.5) - PAD_Y}
          fill="var(--risk-critical, #b91c1c)"
          opacity={0.04}
        />

        {/* Grid + ticks */}
        {scoreTicks.map((tick) => (
          <g key={`score-${tick}`}>
            <line
              x1={sx(tick)}
              y1={PAD_Y}
              x2={sx(tick)}
              y2={H - PAD_Y}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1}
            />
            <text
              x={sx(tick)}
              y={H - PAD_Y + 16}
              textAnchor="middle"
              fontSize={9}
              fill="var(--ink-muted, #71717a)"
            >
              {tick}
            </text>
          </g>
        ))}
        {velTickValues.map((tick) => (
          <g key={`vel-${tick}`}>
            <line
              x1={PAD_X}
              y1={sy(tick)}
              x2={W - PAD_Y}
              y2={sy(tick)}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1}
            />
            <text
              x={PAD_X - 10}
              y={sy(tick) + 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--ink-muted, #71717a)"
            >
              {formatVelocityTick(tick)}
            </text>
          </g>
        ))}

        {/* Axes */}
        <line x1={PAD_X} y1={H - PAD_Y} x2={W - PAD_Y} y2={H - PAD_Y} stroke="var(--paper-line, #e4e4e7)" strokeWidth={1} />
        <line x1={PAD_X} y1={PAD_Y} x2={PAD_X} y2={H - PAD_Y} stroke="var(--paper-line, #e4e4e7)" strokeWidth={1} />

        {/* Axis labels */}
        <text x={W / 2} y={H - 8} textAnchor="middle" fontSize={11} fill="var(--ink-muted, #71717a)">
          Drift score
        </text>
        <text
          x={14}
          y={H / 2}
          textAnchor="middle"
          fontSize={11}
          fill="var(--ink-muted, #71717a)"
          transform={`rotate(-90 14 ${H / 2})`}
        >
          Drift velocity
        </text>

        {/* Threshold guides */}
        <line
          x1={sx(55)}
          y1={PAD_Y}
          x2={sx(55)}
          y2={H - PAD_Y}
          stroke="var(--ink-faint, #a1a1aa)"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <line
          x1={sx(55)}
          y1={sy(rawMax * 0.5)}
          x2={W - PAD_Y}
          y2={sy(rawMax * 0.5)}
          stroke="var(--ink-faint, #a1a1aa)"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <text x={sx(55) + 4} y={PAD_Y + 12} fontSize={9} fill="var(--ink-muted, #71717a)">
          priority zone
        </text>

        {/* Dots */}
        {customers.map((c) => {
          const selected = c.drift_id === selectedId;
          return (
            <g key={c.drift_id}>
              <circle
                cx={sx(c.drift_score)}
                cy={sy(c.drift_velocity)}
                r={selected ? 9 : 6}
                fill={dotColor(c.velocity_band)}
                opacity={selected ? 1 : 0.78}
                stroke={selected ? "var(--ink, #0a0a0b)" : "white"}
                strokeWidth={selected ? 2 : 1}
                className="cursor-pointer transition-all"
                onClick={() => onSelect(c.drift_id)}
              />
              {(selected || c.drift_score > 55) && (
                <text
                  x={sx(c.drift_score)}
                  y={sy(c.drift_velocity) - 12}
                  textAnchor="middle"
                  fontSize={10}
                  fill="var(--ink-soft, #3f3f46)"
                  fontWeight={selected ? 600 : 400}
                  className="pointer-events-none"
                >
                  {c.name.split(" ")[0]}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Customer list — click to select (easier than hunting for dots) */}
      <div className="mt-3 border-t border-paper-line pt-2 space-y-0.5 max-h-56 overflow-y-auto">
        {customers.map((c) => {
          const selected = c.drift_id === selectedId;
          return (
            <button
              key={c.drift_id}
              onClick={() => onSelect(c.drift_id)}
              className={cn(
                "w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors",
                selected ? "bg-accent-bg" : "hover:bg-paper-sunken",
              )}
            >
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ background: dotColor(c.velocity_band) }}
              />
              <span className={cn("text-xs flex-1 min-w-0 truncate", selected ? "text-accent font-medium" : "text-ink")}>
                {c.name}
              </span>
              {c.causal_label === "benign" && (
                <span className="text-2xs px-1.5 py-0.5 rounded bg-risk-low-bg text-risk-low shrink-0">
                  ✓ benign
                </span>
              )}
              {c.causal_label === "risk" && (
                <span className="text-2xs px-1.5 py-0.5 rounded bg-risk-critical-bg text-risk-critical shrink-0">
                  risk
                </span>
              )}
              {c.is_suspicious && (
                <span className="text-2xs px-1.5 py-0.5 rounded bg-risk-high text-white shrink-0">
                  slow
                </span>
              )}
              {c.is_dormancy_break && (
                <span className="text-2xs px-1.5 py-0.5 rounded bg-risk-critical text-white shrink-0">
                  dormant
                </span>
              )}
              {c.is_name_changed && (
                <span className="text-2xs px-1.5 py-0.5 rounded bg-risk-medium text-white shrink-0">
                  name
                </span>
              )}
              <span className="font-mono text-2xs tabular text-ink-soft w-8 text-right shrink-0">
                {c.drift_score.toFixed(0)}
              </span>
            </button>
          );
        })}
      </div>
    </ZoomablePanel>
  );
}
