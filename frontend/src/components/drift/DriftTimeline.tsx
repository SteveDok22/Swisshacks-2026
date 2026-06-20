"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
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
  const { timeline, sanctions_month, drift_start_month, news_spike_month } =
    detail;
  const [cursor, setCursor] = useState(timeline.length - 1);

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

  const maxVel = Math.max(1, ...timeline.map((p) => p.velocity));
  const months = timeline.map((p) => p.month);
  const minMonth = Math.min(...months);
  const maxMonth = Math.max(...months);

  const mx = (m: number) =>
    PAD + ((m - minMonth) / Math.max(1, maxMonth - minMonth)) * (W - 2 * PAD);
  const vy = (v: number) => H - PAD - (v / maxVel) * (H - 2 * PAD);

  // Find the month where the Drift Engine first flags (velocity >= 0.8)
  const alertPoint = timeline.find((p) => p.velocity >= 0.8);
  const alertMonth = alertPoint?.month ?? null;

  // BOCPD regime change — the month the run-length posterior reset (the
  // behavioral changepoint). Rendered as a dashed marker.
  const changepointPoint = timeline.find((p) => p.bocpd_changepoint);
  const changepointMonth = changepointPoint?.month ?? null;

  // News-volume spike (UC1) — the month a sustained external news spike broke,
  // the public anchor of the confirmation-lift window. It is an analysis value
  // (not a timeline point), so only render it when it lands inside the plotted
  // window. Rendered as a distinct cyan dashed marker.
  const newsSpikeMonth =
    news_spike_month !== null &&
    news_spike_month >= minMonth &&
    news_spike_month <= maxMonth
      ? news_spike_month
      : null;

  const leadTime =
    alertMonth !== null && sanctions_month !== null
      ? sanctions_month - alertMonth
      : null;

  const path = timeline
    .map((p, i) => `${i === 0 ? "M" : "L"} ${mx(p.month)} ${vy(p.velocity)}`)
    .join(" ");

  const current = timeline[Math.min(cursor, timeline.length - 1)];

  return (
    <div className="border border-paper-line rounded bg-paper-raised p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Drift Timeline</h3>
          <p className="text-2xs text-ink-muted mt-0.5">
            Velocity over time. Drag the slider to replay.
          </p>
        </div>
        {leadTime !== null && leadTime > 0 && (
          <div className="text-right">
            <div className="font-mono text-lg font-semibold text-risk-high tabular">
              {leadTime} mo
            </div>
            <div className="text-2xs text-ink-muted">advance warning</div>
          </div>
        )}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Axes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#e4e4e7" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#e4e4e7" />

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

        {/* Drift start marker */}
        {drift_start_month !== null && (
          <line
            x1={mx(drift_start_month)}
            y1={PAD}
            x2={mx(drift_start_month)}
            y2={H - PAD}
            stroke="#a1a1aa"
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

        {/* News-spike marker (UC1) — external news-volume regime change */}
        {newsSpikeMonth !== null && (
          <g>
            <line
              x1={mx(newsSpikeMonth)}
              y1={PAD}
              x2={mx(newsSpikeMonth)}
              y2={H - PAD}
              stroke="#0891b2"
              strokeWidth={1.5}
              strokeDasharray="5 3"
              opacity={0.8}
            />
            <text
              x={mx(newsSpikeMonth) + 4}
              y={H - PAD - 16}
              fontSize={9}
              fill="#0891b2"
              fontWeight={600}
            >
              News spike
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
          stroke="#0a0a0b"
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
    </div>
  );
}
