"use client";

import { useState } from "react";
import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { ContagionGraphData } from "@/types/api";

interface ContagionGraphProps {
  data: ContagionGraphData;
  selectedId: string | null;
}

/**
 * Ownership contagion graph.
 *
 * Shows how risk propagates from a sanctioned entity (the seed, deep red)
 * through shell companies to bank customers who are themselves on no list.
 * Node colour intensity = propagated risk (personalized PageRank).
 *
 * When the selected customer is in the graph it is highlighted. When it is
 * not connected to any flagged structure the panel shows a "not in network"
 * status instead, with an option to expand the full network for context.
 */
export function ContagionGraph({ data, selectedId }: ContagionGraphProps) {
  const [showFullGraph, setShowFullGraph] = useState(false);

  const W = 560;
  const H = 360;
  const explanation =
    "Network layout, not a time chart. Vertical layers show entity role: source companies at top, ownership intermediaries in the middle, bank customers at the bottom. Node color is propagated risk; edge thickness is ownership stake. The number inside a customer node is the hop distance from the flagged seed entity.";

  const layerGuides = [
    { y: 60, label: "Source entities" },
    { y: 180, label: "Ownership intermediaries" },
    { y: 300, label: "Bank customers" },
  ];

  // Layered layout by entity type
  const layers: Record<string, number> = {
    company: 0,
    shell: 1,
    individual: 2,
  };

  // Assign y by layer, x spread within layer
  const byLayer: Record<number, string[]> = { 0: [], 1: [], 2: [] };
  data.nodes.forEach((n) => {
    const layer = n.is_seed ? 0 : (layers[n.entity_type] ?? 1);
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

  // Is the currently selected customer in this contagion graph?
  const selectedNode = selectedId
    ? data.nodes.find((n) => n.id === selectedId)
    : null;
  const selectedInGraph = !!selectedNode;

  // Name of the selected entity for the "not connected" card
  const selectedName = selectedNode?.name ?? selectedId ?? "This entity";

  // Affected customers (non-seed, with elevated risk)
  const affectedCustomers = data.nodes.filter(
    (n) => n.is_customer && !n.is_seed && n.risk > 0.01
  );

  const graph = (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {layerGuides.map((layer) => (
          <g key={layer.label}>
            <line
              x1={12} y1={layer.y}
              x2={W - 12} y2={layer.y}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1}
            />
            <text x={12} y={layer.y - 16} fontSize={10} fill="var(--ink-muted, #71717a)">
              {layer.label}
            </text>
          </g>
        ))}

        {data.edges.map((e, i) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          return (
            <line
              key={i}
              x1={a.x} y1={a.y}
              x2={b.x} y2={b.y}
              stroke="var(--paper-line, #e4e4e7)"
              strokeWidth={1 + e.stake * 3}
            />
          );
        })}

        {data.nodes.map((n) => {
          const p = pos[n.id];
          if (!p) return null;
          const color = riskColor(n.risk, n.is_seed);
          const r = n.is_seed ? 14 : n.is_customer ? 11 : 9;
          const isSelected = n.id === selectedId;
          return (
            <g key={n.id}>
              {/* Highlight ring for the currently viewed customer */}
              {isSelected && (
                <circle
                  cx={p.x} cy={p.y}
                  r={r + 6}
                  fill="none"
                  stroke="var(--accent, #2563eb)"
                  strokeWidth={2}
                  strokeDasharray="4 2"
                />
              )}
              <circle
                cx={p.x} cy={p.y}
                r={r}
                fill={color}
                opacity={n.risk > 0.01 || n.is_seed ? 0.9 : 0.5}
                stroke={n.is_customer ? "var(--ink, #0a0a0b)" : "white"}
                strokeWidth={isSelected ? 2 : n.is_customer ? 1.5 : 1}
              />
              <text
                x={p.x}
                y={p.y + r + 12}
                textAnchor="middle"
                fontSize={9}
                fill={isSelected ? "var(--accent, #2563eb)" : "var(--ink-soft, #3f3f46)"}
                fontWeight={n.is_seed || isSelected ? 600 : 400}
              >
                {n.name.length > 18 ? n.name.slice(0, 16) + "…" : n.name}
              </text>
              {isSelected && (
                <text
                  x={p.x}
                  y={p.y + r + 22}
                  textAnchor="middle"
                  fontSize={8}
                  fill="var(--accent, #2563eb)"
                >
                  ← viewing
                </text>
              )}
              {/* Hop distance label inside customer nodes */}
              {n.hops_from_seed != null && n.hops_from_seed > 0 && n.is_customer && (
                <text
                  x={p.x} y={p.y + 3}
                  textAnchor="middle"
                  fontSize={8}
                  fill="white"
                  fontWeight={600}
                >
                  {n.hops_from_seed}
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
        <span className="flex items-center gap-1.5">
          <span
            className="inline-flex items-center justify-center h-4 w-4 rounded-full text-white text-2xs font-bold"
            style={{ background: "var(--risk-critical, #b91c1c)", fontSize: 8 }}
          >
            2
          </span>
          = hops from flagged entity
        </span>
      </div>
    </>
  );

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Ownership Contagion graph"
    >
      <div className="mb-3 flex items-start justify-between gap-3 pr-10">
        <div>
          <h3 className="text-sm font-semibold text-ink">Ownership Contagion</h3>
          {selectedInGraph && (
            <p className="text-2xs text-accent mt-0.5">
              This entity is in the flagged ownership network
            </p>
          )}
        </div>
        <InfoHint text={explanation} />
      </div>

      {selectedInGraph ? (
        /* Entity IS in the graph — show it, highlighted */
        graph
      ) : (
        /* Entity is NOT in the graph — show a clear status card */
        <div className="space-y-3">
          <div className="flex items-start gap-3 rounded border border-paper-line bg-paper p-3">
            <span className="text-base leading-none mt-0.5">✓</span>
            <div className="min-w-0">
              <p className="text-xs font-medium text-ink">
                Not connected to any flagged ownership structure
              </p>
              <p className="text-2xs text-ink-muted mt-0.5">
                {selectedName} has no known ownership link to any currently
                sanctioned or flagged entity in the monitored book.
              </p>
            </div>
          </div>

          {/* Affected customers summary */}
          {affectedCustomers.length > 0 && (
            <div className="rounded border border-paper-line bg-paper px-3 py-2">
              <p className="text-2xs text-ink-muted mb-1.5">
                Customers with elevated contagion risk in this book:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {affectedCustomers.map((n) => (
                  <span
                    key={n.id}
                    className="text-2xs px-1.5 py-0.5 rounded font-medium"
                    style={{
                      background: "var(--risk-critical-bg, #fef2f2)",
                      color: "var(--risk-critical, #b91c1c)",
                    }}
                  >
                    {n.name.length > 22 ? n.name.slice(0, 20) + "…" : n.name}
                    <span className="opacity-60 ml-1">
                      ({n.hops_from_seed != null ? `${n.hops_from_seed} hops` : "connected"})
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Toggle to still view the full network */}
          <button
            onClick={() => setShowFullGraph((v) => !v)}
            className="text-2xs text-ink-muted hover:text-ink underline underline-offset-2 transition-colors"
          >
            {showFullGraph ? "Hide full ownership network" : "View full ownership network"}
          </button>

          {showFullGraph && graph}
        </div>
      )}
    </ZoomablePanel>
  );
}
