"use client";

import { cn } from "@/lib/utils";
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
  const PAD = 44;

  const maxScore = 100;
  const maxVel = Math.max(4, ...customers.map((c) => c.drift_velocity));

  const sx = (score: number) => PAD + (score / maxScore) * (W - 2 * PAD);
  const sy = (vel: number) => H - PAD - (vel / maxVel) * (H - 2 * PAD);

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
    <div className="border border-paper-line rounded bg-paper-raised p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Drift Radar</h3>
          <p className="text-2xs text-ink-muted mt-0.5">
            Score x Velocity. Upper-right = highest priority.
          </p>
        </div>
        <div className="flex items-center gap-3 text-2xs text-ink-muted">
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
          y={PAD}
          width={W - PAD - sx(55)}
          height={sy(maxVel * 0.5) - PAD}
          fill="var(--risk-critical, #b91c1c)"
          opacity={0.04}
        />

        {/* Axes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#e4e4e7" strokeWidth={1} />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#e4e4e7" strokeWidth={1} />

        {/* Axis labels */}
        <text x={W / 2} y={H - 8} textAnchor="middle" fontSize={11} fill="#71717a">
          Drift score →
        </text>
        <text
          x={14}
          y={H / 2}
          textAnchor="middle"
          fontSize={11}
          fill="#71717a"
          transform={`rotate(-90 14 ${H / 2})`}
        >
          Drift velocity →
        </text>

        {/* Threshold guides */}
        <line
          x1={sx(55)}
          y1={PAD}
          x2={sx(55)}
          y2={H - PAD}
          stroke="#d4d4d8"
          strokeWidth={1}
          strokeDasharray="3 3"
        />

        {/* Dots */}
        {customers.map((c) => {
          const selected = c.customer_id === selectedId;
          return (
            <g key={c.customer_id}>
              <circle
                cx={sx(c.drift_score)}
                cy={sy(c.drift_velocity)}
                r={selected ? 9 : 6}
                fill={dotColor(c.velocity_band)}
                opacity={selected ? 1 : 0.78}
                stroke={selected ? "#0a0a0b" : "white"}
                strokeWidth={selected ? 2 : 1}
                className="cursor-pointer transition-all"
                onClick={() => onSelect(c.customer_id)}
              />
              {(selected || c.drift_score > 55) && (
                <text
                  x={sx(c.drift_score)}
                  y={sy(c.drift_velocity) - 12}
                  textAnchor="middle"
                  fontSize={10}
                  fill="#3f3f46"
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
    </div>
  );
}
