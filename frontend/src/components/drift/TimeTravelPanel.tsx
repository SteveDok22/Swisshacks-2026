"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { driftApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { History, ShieldCheck, Loader2 } from "lucide-react";

interface TimeTravelPanelProps {
  customerId: string;
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
export function TimeTravelPanel({ customerId }: TimeTravelPanelProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["drift-replay", customerId],
    queryFn: () => driftApi.replay(customerId),
  });

  const [cursor, setCursor] = useState<number | null>(null);

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
  const PAD = 36;

  const months = data.points.map((p) => p.month);
  const minM = Math.min(...months);
  const maxM = Math.max(...months);
  const maxScore = 100;

  const mx = (m: number) => PAD + ((m - minM) / Math.max(1, maxM - minM)) * (W - 2 * PAD);
  const sy = (s: number) => H - PAD - (s / maxScore) * (H - 2 * PAD);

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
    <div className="border border-paper-line rounded bg-paper-raised p-4">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <History className="h-3.5 w-3.5 text-accent" strokeWidth={2} />
          <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
            Time-Travel Audit — what would we have known?
          </h3>
        </div>
        {data.lead_time_months !== null && data.lead_time_months > 0 && (
          <div className="text-right">
            <span className="font-mono text-lg font-semibold text-risk-high tabular">
              {data.lead_time_months} mo
            </span>
            <span className="text-2xs text-ink-muted ml-1">audited lead</span>
          </div>
        )}
      </div>

      <p className="text-2xs text-ink-faint mb-3">
        Score recomputed using only data available at each month. No future
        information leaks backward.
      </p>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Axes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#e4e4e7" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#e4e4e7" />

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
        <text x={W - PAD} y={sy(data.alert_threshold) - 4} textAnchor="end" fontSize={9} fill="#a16207">
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
            <text x={mx(data.alert_month) + 4} y={PAD + 10} fontSize={9} fill="var(--risk-high,#c2410c)" fontWeight={600}>
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
            <text x={mx(data.sanctions_month) - 4} y={PAD + 10} fontSize={9} fill="var(--risk-critical,#b91c1c)" fontWeight={600} textAnchor="end">
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
          <AsOfStat label="Velocity" value={cur.velocity.toFixed(1)} />
          <AsOfStat label="Public" value={cur.public_risk.toFixed(2)} />
          <AsOfStat label="Contagion" value={cur.contagion_active ? "active" : "—"} />
        </div>
      </div>

      {/* Proof line */}
      <div className="flex items-start gap-2 mt-3 text-2xs text-ink-muted">
        <ShieldCheck className="h-3.5 w-3.5 text-risk-low shrink-0 mt-0.5" strokeWidth={2} />
        <span>
          Verifiable property: corrupting any month after T leaves the as-of-T
          score unchanged. BOCPD is online by construction — no look-ahead.
        </span>
      </div>
    </div>
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
