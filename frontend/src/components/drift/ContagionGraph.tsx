"use client";

import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { ContagionGraphData } from "@/types/api";

interface ContagionGraphProps {
  data: ContagionGraphData;
}

/**
 * Ownership contagion graph.
 *
 * Shows how risk propagates from a sanctioned entity (the seed, deep red)
 * through shell companies to bank customers who are themselves on no list.
 * Node colour intensity = propagated risk (personalized PageRank).
 *
 * Layout: simple deterministic layered placement (seed at top, shells in
 * the middle, customers at the bottom) — no force simulation needed for a
 * graph this size, and deterministic layout means the demo looks identical
 * every run.
 */
export function ContagionGraph({ data }: ContagionGraphProps) {
  const W = 560;
  const H = 360;
  const explanation =
    "Network layout, not a time chart. Vertical layers show entity role: source companies at top, ownership intermediaries in the middle, bank customers at the bottom. Node color is propagated risk; edge thickness is ownership stake.";
  const layerGuides = [
    { y: 60, label: "Source entities" },
    { y: 180, label: "Ownership intermediaries" },
    { y: 300, label: "Bank customers" },
  ];

  // Layered layout by entity type
  const layers: Record<string, number> = {
    company: 0, // sanctioned seed + clean holdings at top
    shell: 1,
    individual: 2, // customers at bottom
  };

  // Assign y by layer, x spread within layer
  const byLayer: Record<number, string[]> = { 0: [], 1: [], 2: [] };
  data.nodes.forEach((n) => {
    const layer = n.is_seed ? 0 : layers[n.entity_type] ?? 1;
    byLayer[layer].push(n.id);
  });

  const pos: Record<string, { x: number; y: number }> = {};
  Object.entries(byLayer).forEach(([layerStr, ids]) => {
    const layer = Number(layerStr);
    const y = 60 + layer * 120;
    ids.forEach((id, i) => {
      const x = ((i + 1) / (ids.length + 1)) * W;
      pos[id] = { x, y };
    });
  });

  const riskColor = (risk: number, isSeed: boolean) => {
    if (isSeed) return "#7f1d1d";
    if (risk > 0.15) return "var(--risk-critical, #b91c1c)";
    if (risk > 0.05) return "var(--risk-high, #c2410c)";
    if (risk > 0.01) return "var(--risk-medium, #a16207)";
    return "var(--ink-faint, #a1a1aa)";
  };

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Ownership Contagion graph"
    >
      <div className="mb-3 flex items-start justify-between gap-3 pr-10">
        <h3 className="text-sm font-semibold text-ink">Ownership Contagion</h3>
        <InfoHint text={explanation} />
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Layer labels: this graph is a network layout, not a numeric axis. */}
        {layerGuides.map((layer) => (
          <g key={layer.label}>
            <line
              x1={12}
              y1={layer.y}
              x2={W - 12}
              y2={layer.y}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1}
            />
            <text x={12} y={layer.y - 16} fontSize={10} fill="var(--ink-muted, #71717a)">
              {layer.label}
            </text>
          </g>
        ))}

        {/* Edges */}
        {data.edges.map((e, i) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1 + e.stake * 3}
            />
          );
        })}

        {/* Nodes */}
        {data.nodes.map((n) => {
          const p = pos[n.id];
          if (!p) return null;
          const color = riskColor(n.risk, n.is_seed);
          const r = n.is_seed ? 14 : n.is_customer ? 11 : 9;
          return (
            <g key={n.id}>
              <circle
                cx={p.x}
                cy={p.y}
                r={r}
                fill={color}
                opacity={n.risk > 0.01 || n.is_seed ? 0.9 : 0.5}
                stroke={n.is_customer ? "var(--ink, #0a0a0b)" : "white"}
                strokeWidth={n.is_customer ? 1.5 : 1}
              />
              <text
                x={p.x}
                y={p.y + r + 12}
                textAnchor="middle"
                fontSize={9}
                fill="var(--ink-soft, #3f3f46)"
                fontWeight={n.is_seed ? 600 : 400}
              >
                {n.name.length > 18 ? n.name.slice(0, 16) + "…" : n.name}
              </text>
              {n.hops_from_seed !== null && n.hops_from_seed > 0 && n.is_customer && (
                <text
                  x={p.x}
                  y={p.y + 3}
                  textAnchor="middle"
                  fontSize={8}
                  fill="white"
                  fontWeight={600}
                >
                  {n.hops_from_seed}h
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-2xs text-ink-muted mt-2">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#7f1d1d" }} />
          Sanctioned seed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-ink" style={{ background: "var(--risk-critical, #b91c1c)" }} />
          Affected customer
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--ink-faint, #a1a1aa)" }} />
          Clean
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-px w-6 bg-ink-faint" />
          Thicker line = larger stake
        </span>
      </div>
    </ZoomablePanel>
  );
}
