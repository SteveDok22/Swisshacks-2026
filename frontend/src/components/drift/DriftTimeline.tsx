"use client";

import { useState } from "react";
import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { DriftCustomerDetail } from "@/types/api";

interface DriftTimelineProps {
  detail: DriftCustomerDetail;
}

/**
 * Timeline scrubber — the demo killer.
 *
 * Drag through the customer's months of history and watch drift velocity
 * climb. Two markers tell the whole story:
 *   - "Drift Engine flags here" (when velocity crosses the alert band)
 *   - "Sanctions list catches here" (month 0, the lagging event)
 *
 * The gap between them is the lead time — the entire value proposition.
 */
export function DriftTimeline({ detail }: DriftTimelineProps) {
  const { timeline, sanctions_month, drift_start_month } = detail;
  const [cursor, setCursor] = useState(timeline.length - 1);
  const explanation =
    "Past timeline of observed drift velocity. X-axis is historical month; Y-axis is velocity in bits per month. Values above the alert band indicate the behaviour is changing fast enough to flag before any sanctions event.";

  if (timeline.length === 0) {
    return (
      <div className="border border-paper-line rounded bg-paper-raised p-4 text-sm text-ink-muted">
        No timeline data for this customer.
      </div>
    );
  }

  const W = 640;
  const H = 200;
  const PAD = 36;

  const minVel = Math.min(0, ...timeline.map((p) => p.velocity));
  const maxVel = Math.max(1, ...timeline.map((p) => p.velocity));
  const months = timeline.map((p) => p.month);
  const minMonth = Math.min(...months);
  const maxMonth = Math.max(...months);

  const mx = (m: number) =>
    PAD + ((m - minMonth) / Math.max(1, maxMonth - minMonth)) * (W - 2 * PAD);
  const vy = (v: number) =>
    H - PAD - ((v - minVel) / Math.max(0.1, maxVel - minVel)) * (H - 2 * PAD);
  const monthTickCount = Math.min(5, Math.max(2, maxMonth - minMonth + 1));
  const monthTicks = Array.from(
    new Set(
      Array.from({ length: monthTickCount }, (_, i) =>
        Math.round(minMonth + (i / Math.max(1, monthTickCount - 1)) * (maxMonth - minMonth)),
      ),
    ),
  );
  const velocityTicks = Array.from(
    new Set([minVel, 0, 0.8, maxVel].map((tick) => Number(tick.toFixed(1)))),
  ).sort((a, b) => a - b);

  // Find the month where the Drift Engine first flags (velocity >= 0.8)
  const alertPoint = timeline.find((p) => p.velocity >= 0.8);
  const alertMonth = alertPoint?.month ?? null;

  // BOCPD regime change — the month the run-length posterior reset (the
  // behavioral changepoint). Rendered as a dashed marker.
  const changepointPoint = timeline.find((p) => p.bocpd_changepoint);
  const changepointMonth = changepointPoint?.month ?? null;

  const leadTime =
    alertMonth !== null && sanctions_month !== null
      ? sanctions_month - alertMonth
      : null;

  const path = timeline
    .map((p, i) => `${i === 0 ? "M" : "L"} ${mx(p.month)} ${vy(p.velocity)}`)
    .join(" ");

  const current = timeline[Math.min(cursor, timeline.length - 1)];

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Drift Timeline"
    >
      <div className="flex items-center justify-between mb-3 pr-10">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-ink">Drift Timeline</h3>
          <InfoHint text={explanation} />
        </div>
        {leadTime !== null && leadTime > 0 && (
          <div className="text-right whitespace-nowrap">
            <span className="font-mono text-lg font-semibold text-risk-high tabular">
              {leadTime} mo
            </span>
            <span className="text-2xs text-ink-muted ml-1">advance warning</span>
          </div>
        )}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Grid + ticks */}
        {velocityTicks.map((tick) => (
          <g key={`vel-${tick}`}>
            <line
              x1={PAD}
              y1={vy(tick)}
              x2={W - PAD}
              y2={vy(tick)}
              stroke={tick === 0 ? "var(--paper-line, #e4e4e7)" : "var(--paper-raised, #ffffff)"}
              strokeWidth={tick === 0 ? 1.25 : 1}
            />
            <text
              x={PAD - 8}
              y={vy(tick) + 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--ink-muted, #71717a)"
            >
              {tick.toFixed(1)}
            </text>
          </g>
        ))}
        {monthTicks.map((tick) => (
          <g key={`month-${tick}`}>
            <line
              x1={mx(tick)}
              y1={H - PAD}
              x2={mx(tick)}
              y2={H - PAD + 4}
              stroke="var(--ink-faint, #a1a1aa)"
              strokeWidth={1}
            />
            <text
              x={mx(tick)}
              y={H - PAD + 16}
              textAnchor="middle"
              fontSize={9}
              fill="var(--ink-muted, #71717a)"
            >
              m{tick}
            </text>
          </g>
        ))}

        {/* Axes */}
        <line x1={PAD} y1={vy(0)} x2={W - PAD} y2={vy(0)} stroke="var(--paper-line, #e4e4e7)" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="var(--paper-line, #e4e4e7)" />
        <text x={W / 2} y={H - 7} textAnchor="middle" fontSize={10} fill="var(--ink-muted, #71717a)">
          Month in observed history
        </text>
        <text
          x={13}
          y={H / 2}
          textAnchor="middle"
          fontSize={10}
          fill="var(--ink-muted, #71717a)"
          transform={`rotate(-90 13 ${H / 2})`}
        >
          Drift velocity (bits/mo)
        </text>

        {/* Alert band threshold */}
        <line
          x1={PAD}
          y1={vy(0.8)}
          x2={W - PAD}
          y2={vy(0.8)}
          stroke="var(--risk-medium, #a16207)"
          strokeWidth={1}
          strokeDasharray="4 4"
          opacity={0.5}
        />
        <text x={W - PAD} y={vy(0.8) - 5} textAnchor="end" fontSize={9} fill="var(--risk-medium, #a16207)">
          alert band 0.8 bits/mo
        </text>

        {/* Drift start marker */}
        {drift_start_month !== null && (
          <line
            x1={mx(drift_start_month)}
            y1={PAD}
            x2={mx(drift_start_month)}
            y2={H - PAD}
            stroke="var(--ink-faint, #a1a1aa)"
            strokeWidth={1}
            strokeDasharray="2 3"
          />
        )}

        {/* BOCPD regime-change marker (dashed) */}
        {changepointMonth !== null && (
          <g>
            <line
              x1={mx(changepointMonth)}
              y1={PAD}
              x2={mx(changepointMonth)}
              y2={H - PAD}
              stroke="var(--accent-2, #7c3aed)"
              strokeWidth={1.5}
              strokeDasharray="5 3"
              opacity={0.8}
            />
            <text
              x={mx(changepointMonth) + 4}
              y={H - PAD - 4}
              fontSize={9}
              fill="var(--accent-2, #7c3aed)"
              fontWeight={600}
            >
              Regime change
            </text>
          </g>
        )}

        {/* Drift Engine flags marker (leading) */}
        {alertMonth !== null && (
          <g>
            <line
              x1={mx(alertMonth)}
              y1={PAD}
              x2={mx(alertMonth)}
              y2={H - PAD}
              stroke="var(--risk-high, #c2410c)"
              strokeWidth={2}
            />
            <text
              x={mx(alertMonth) + 4}
              y={PAD + 12}
              fontSize={9}
              fill="var(--risk-high, #c2410c)"
              fontWeight={600}
            >
              Drift Engine flags
            </text>
          </g>
        )}

        {/* Sanctions marker (lagging) */}
        {sanctions_month !== null && (
          <g>
            <line
              x1={mx(sanctions_month)}
              y1={PAD}
              x2={mx(sanctions_month)}
              y2={H - PAD}
              stroke="var(--risk-critical, #b91c1c)"
              strokeWidth={2}
            />
            <text
              x={mx(sanctions_month) - 4}
              y={PAD + 12}
              fontSize={9}
              fill="var(--risk-critical, #b91c1c)"
              fontWeight={600}
              textAnchor="end"
            >
              Sanctions hit
            </text>
          </g>
        )}

        {/* Velocity curve */}
        <path d={path} fill="none" stroke="var(--accent, #003d4c)" strokeWidth={2} />

        {/* Cursor */}
        <line
          x1={mx(current.month)}
          y1={PAD}
          x2={mx(current.month)}
          y2={H - PAD}
          stroke="var(--ink, #0a0a0b)"
          strokeWidth={1}
          opacity={0.3}
        />
        <circle
          cx={mx(current.month)}
          cy={vy(current.velocity)}
          r={5}
          fill="var(--accent, #003d4c)"
          stroke="white"
          strokeWidth={2}
        />
      </svg>

      {/* Slider */}
      <input
        type="range"
        min={0}
        max={timeline.length - 1}
        value={cursor}
        onChange={(e) => setCursor(Number(e.target.value))}
        className="w-full mt-2 accent-accent"
      />

      {/* Current readout */}
      <div className="flex items-center justify-between mt-2 text-xs">
        <span className="text-ink-muted">
          Month <span className="font-mono text-ink">{current.month}</span>
        </span>
        <span className="text-ink-muted">
          Velocity{" "}
          <span className="font-mono text-ink tabular">
            {current.velocity.toFixed(2)}
          </span>{" "}
          bits/mo
        </span>
        <span className="text-ink-muted">
          Drift{" "}
          <span className="font-mono text-ink tabular">
            {current.drift_bits.toFixed(2)}
          </span>{" "}
          bits
        </span>
      </div>
    </ZoomablePanel>
  );
}
