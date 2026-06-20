"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { driftApi } from "@/lib/api";
import { cn, formatCompact, evenTicks } from "@/lib/utils";
import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import { History, Loader2 } from "lucide-react";

interface TimeTravelPanelProps {
  driftId: string;
}

/**
 * Time-Travel Audit panel — as-of replay proving no look-ahead.
 *
 * Drag the slider to "freeze time" at month T. The score shown is what the
 * system WOULD have produced using only data up to T — the contagion line
 * only activates once the sanctions listing actually happened, public signals
 * only count if dated <= T. The gap between when the system would have flagged
 * and when sanctions hit is the audited lead time.
 *
 * This is the regulatory proof: not a chart, but a verifiable property.
 */
export function TimeTravelPanel({ driftId }: TimeTravelPanelProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["drift-replay", driftId],
    queryFn: () => driftApi.replay(driftId),
  });

  const [cursor, setCursor] = useState<number | null>(null);
  const explanation =
    "Past-only replay. Score is recomputed using only data available at each selected month; no future information leaks backward. Verifiable property: corrupting any month after T leaves the as-of-T score unchanged. BOCPD is online by construction. Audited lead is the gap between when the system first crossed the alert threshold and when sanctions hit.";

  if (isLoading) {
    return (
      <div className="border border-paper-line rounded bg-paper-raised p-4 flex items-center gap-2 text-sm text-ink-muted">
        <Loader2 className="h-4 w-4 animate-spin" /> Replaying history…
      </div>
    );
  }
  if (!data || data.points.length === 0) return null;

  const W = 640;
  const H = 200;
  const PAD = 44;

  const months = data.points.map((p) => p.month);
  const minM = Math.min(...months);
  const maxM = Math.max(...months);
  const maxScore = 100;

  const mx = (m: number) => PAD + ((m - minM) / Math.max(1, maxM - minM)) * (W - 2 * PAD);
  const sy = (s: number) => H - PAD - (s / maxScore) * (H - 2 * PAD);
  const monthTicks = evenTicks(minM, maxM);
  const scoreTicks = Array.from(
    new Set([0, 50, data.alert_threshold, 100].map((tick) => Math.round(tick))),
  ).sort((a, b) => a - b);

  const curIdx = cursor ?? data.points.length - 1;
  const cur = data.points[Math.min(curIdx, data.points.length - 1)];

  const path = data.points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${mx(p.month)} ${sy(p.as_of_score)}`)
    .join(" ");

  // Path only up to cursor (the "known so far" portion)
  const knownPath = data.points
    .filter((p) => p.month <= cur.month)
    .map((p, i) => `${i === 0 ? "M" : "L"} ${mx(p.month)} ${sy(p.as_of_score)}`)
    .join(" ");

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Time-Travel Audit"
    >
      <div className="flex items-start justify-between gap-3 mb-3 pr-10">
        <div className="flex items-center gap-2">
          <History className="h-3.5 w-3.5 text-accent" strokeWidth={2} />
          <div>
            <h3 className="text-sm font-semibold text-ink">Time-Travel Audit</h3>
            <p className="text-2xs text-ink-muted mt-0.5">
              What would we have known?
            </p>
          </div>
        </div>
        <div className="flex items-start gap-3 shrink-0">
          {data.lead_time_months !== null && data.lead_time_months > 0 && (
            <div className="text-right whitespace-nowrap">
              <span className="font-mono text-lg font-semibold text-risk-high tabular">
                {data.lead_time_months} mo
              </span>
              <span className="text-2xs text-ink-muted ml-1">audited lead</span>
            </div>
          )}
          <InfoHint text={explanation} />
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Grid + ticks */}
        {scoreTicks.map((tick) => (
          <g key={`score-${tick}`}>
            <line
              x1={PAD}
              y1={sy(tick)}
              x2={W - PAD}
              y2={sy(tick)}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1}
            />
            <text
              x={PAD - 8}
              y={sy(tick) + 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--ink-muted, #71717a)"
            >
              {tick}
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
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="var(--paper-line, #e4e4e7)" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="var(--paper-line, #e4e4e7)" />
        <text x={W / 2} y={H - 7} textAnchor="middle" fontSize={10} fill="var(--ink-muted, #71717a)">
          Month in historical replay
        </text>
        <text
          x={13}
          y={H / 2}
          textAnchor="middle"
          fontSize={10}
          fill="var(--ink-muted, #71717a)"
          transform={`rotate(-90 13 ${H / 2})`}
        >
          As-of risk score
        </text>

        {/* Alert threshold */}
        <line
          x1={PAD}
          y1={sy(data.alert_threshold)}
          x2={W - PAD}
          y2={sy(data.alert_threshold)}
          stroke="var(--risk-medium, #a16207)"
          strokeWidth={1}
          strokeDasharray="4 4"
          opacity={0.5}
        />
        <text x={W - PAD} y={sy(data.alert_threshold) - 4} textAnchor="end" fontSize={9} fill="var(--risk-medium, #a16207)">
          alert threshold
        </text>

        {/* Alert month marker (system flags) */}
        {data.alert_month !== null && (
          <g>
            <line
              x1={mx(data.alert_month)}
              y1={PAD}
              x2={mx(data.alert_month)}
              y2={H - PAD}
              stroke="var(--risk-high, #c2410c)"
              strokeWidth={2}
            />
            <text x={mx(data.alert_month) + 4} y={PAD + 10} fontSize={9} fill="var(--risk-high, #c2410c)" fontWeight={600}>
              system flags
            </text>
          </g>
        )}

        {/* Sanctions marker */}
        {data.sanctions_month !== null && (
          <g>
            <line
              x1={mx(data.sanctions_month)}
              y1={PAD}
              x2={mx(data.sanctions_month)}
              y2={H - PAD}
              stroke="var(--risk-critical, #b91c1c)"
              strokeWidth={2}
            />
            <text x={mx(data.sanctions_month) - 4} y={PAD + 10} fontSize={9} fill="var(--risk-critical, #b91c1c)" fontWeight={600} textAnchor="end">
              sanctions hit
            </text>
          </g>
        )}

        {/* Full trajectory (faint) */}
        <path d={path} fill="none" stroke="var(--accent, #003d4c)" strokeWidth={1} opacity={0.2} />
        {/* Known-so-far trajectory (solid) */}
        <path d={knownPath} fill="none" stroke="var(--accent, #003d4c)" strokeWidth={2} />

        {/* Cursor point */}
        <circle cx={mx(cur.month)} cy={sy(cur.as_of_score)} r={5} fill="var(--accent, #003d4c)" stroke="white" strokeWidth={2} />
        <g transform={`translate(${PAD} ${PAD - 18})`}>
          <line x1={0} y1={0} x2={22} y2={0} stroke="var(--accent, #003d4c)" strokeWidth={2} />
          <text x={28} y={3} fontSize={9} fill="var(--ink-muted, #71717a)">known as-of selected month</text>
          <line x1={176} y1={0} x2={198} y2={0} stroke="var(--accent, #003d4c)" strokeWidth={1} opacity={0.2} />
          <text x={204} y={3} fontSize={9} fill="var(--ink-muted, #71717a)">later months, audit context</text>
        </g>
      </svg>

      {/* Slider */}
      <input
        type="range"
        min={0}
        max={data.points.length - 1}
        value={curIdx}
        onChange={(e) => setCursor(Number(e.target.value))}
        className="w-full mt-2 accent-accent"
      />

      {/* As-of readout */}
      <div className="mt-2 p-2 rounded bg-paper-sunken">
        <div className="text-2xs text-ink-muted mb-1">
          As of month <span className="font-mono text-ink">{cur.month}</span>, using only data through then:
        </div>
        <div className="grid grid-cols-4 gap-2 text-center">
          <AsOfStat label="Score" value={cur.as_of_score.toFixed(0)} highlight={cur.as_of_score >= data.alert_threshold} />
          <AsOfStat label="Velocity" value={formatCompact(cur.velocity)} />
          <AsOfStat label="Public risk" value={`${Math.round(cur.public_risk * 100)}`} />
          <AsOfStat label="Contagion" value={cur.contagion_active ? "active" : "—"} />
        </div>
      </div>

    </ZoomablePanel>
  );
}

function AsOfStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className={cn("font-mono text-sm font-semibold tabular", highlight ? "text-risk-high" : "text-ink")}>
        {value}
      </div>
      <div className="text-2xs text-ink-muted">{label}</div>
    </div>
  );
}
