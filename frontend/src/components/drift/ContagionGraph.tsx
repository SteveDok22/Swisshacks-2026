"use client";

import { InfoHint } from "@/components/ui/InfoHint";
import { ZoomablePanel } from "@/components/ui/ZoomablePanel";
import type { ContagionGraphData } from "@/types/api";

interface ContagionGraphProps {
  data: ContagionGraphData;
  selectedId: string | null;
}

/**
 * Ownership contagion graph — shown ONLY when the selected entity is in the
 * flagged ownership network. Hidden for all others.
 *
 * When visible, renders the path from the sanctioned seed down to the
 * selected customer (not the whole book graph), so every node on screen is
 * directly relevant to the entity being reviewed.
 *
 * Layout: deterministic vertical layers — seed at top, intermediaries in
 * the middle, customer at the bottom. No force simulation; deterministic
 * means the demo looks the same every run.
 */
export function ContagionGraph({ data, selectedId }: ContagionGraphProps) {
  // Only show this panel when the selected entity is actually in the graph.
  // Showing the full book contagion structure while viewing an unconnected
  // entity (e.g. Helvetia Pharma) is misleading and confusing.
  if (!selectedId) return null;
  const selectedNode = data.nodes.find((n) => n.id === selectedId);
  if (!selectedNode) return null;

  // --- Build the path from the seed to the selected entity ---
  // Traverse edges from seed → selected via BFS, then trace back the path.
  // All nodes and edges NOT on this path are excluded.
  const seedId = data.seeds[0];
  if (!seedId) return null;

  const adj = new Map<string, string[]>();
  for (const e of data.edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  }

  const parent = new Map<string, string | null>([[seedId, null]]);
  const queue = [seedId];
  while (queue.length > 0) {
    const curr = queue.shift()!;
    if (curr === selectedId) break;
    for (const next of adj.get(curr) ?? []) {
      if (!parent.has(next)) {
        parent.set(next, curr);
        queue.push(next);
      }
    }
  }

  // Trace path back from selected → seed
  const pathNodes = new Set<string>();
  let cur: string | null | undefined = selectedId;
  while (cur != null) {
    pathNodes.add(cur);
    cur = parent.get(cur);
  }

  // If no path found (entity is in the graph but unreachable from seed),
  // show nothing — the contagion story doesn't apply.
  if (!pathNodes.has(seedId)) return null;

  const visibleNodes = data.nodes.filter((n) => pathNodes.has(n.id));
  const visibleEdges = data.edges.filter(
    (e) => pathNodes.has(e.source) && pathNodes.has(e.target)
  );

  // --- Layout ---
  const W = 400;
  const H = 280;
  const explanation =
    "Ownership path from the sanctioned entity down to this customer. Node color = propagated risk (personalized PageRank). Edge thickness = ownership stake. The number inside a customer node is the hop distance from the flagged seed.";

  const layers: Record<string, number> = { company: 0, shell: 1, individual: 2 };
  const byLayer: Record<number, string[]> = { 0: [], 1: [], 2: [] };
  visibleNodes.forEach((n) => {
    byLayer[n.is_seed ? 0 : (layers[n.entity_type] ?? 1)].push(n.id);
  });

  const pos: Record<string, { x: number; y: number }> = {};
  Object.entries(byLayer).forEach(([ls, ids]) => {
    const layer = Number(ls);
    const y = 50 + layer * 95;
    ids.forEach((id, i) => {
      pos[id] = { x: ((i + 1) / (ids.length + 1)) * W, y };
    });
  });

  const riskColor = (risk: number, isSeed: boolean) => {
    if (isSeed) return "#7f1d1d";
    if (risk > 0.15) return "var(--risk-critical, #b91c1c)";
    if (risk > 0.05) return "var(--risk-high, #c2410c)";
    if (risk > 0.01) return "var(--risk-medium, #a16207)";
    return "var(--ink-faint, #a1a1aa)";
  };

  const selectedRisk = selectedNode.risk;

  return (
    <ZoomablePanel
      className="border border-paper-line rounded bg-paper-raised p-4"
      zoomLabel="Zoom Ownership Contagion path"
    >
      <div className="mb-3 flex items-start justify-between gap-3 pr-10">
        <div>
          <h3 className="text-sm font-semibold text-ink">Ownership Contagion</h3>
          <p className="text-2xs text-risk-critical mt-0.5">
            Connected to flagged entity — propagated risk {(selectedRisk * 100).toFixed(0)}%
          </p>
        </div>
        <InfoHint text={explanation} />
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {/* Layer labels */}
        {[
          { y: 50, label: "Sanctioned source" },
          { y: 145, label: "Intermediary" },
          { y: 240, label: "Bank customer (you)" },
        ]
          .filter((lg) => visibleNodes.some((n) => Math.abs(pos[n.id]?.y - lg.y) < 5))
          .map((lg) => (
            <text key={lg.label} x={8} y={lg.y - 18} fontSize={9} fill="var(--ink-muted, #71717a)">
              {lg.label}
            </text>
          ))}

        {/* Edges */}
        {visibleEdges.map((e, i) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          return (
            <g key={i}>
              <line
                x1={a.x} y1={a.y}
                x2={b.x} y2={b.y}
                stroke="var(--paper-line, #e4e4e7)"
                strokeWidth={1 + e.stake * 4}
              />
              {/* Stake label */}
              <text
                x={(a.x + b.x) / 2 + 6}
                y={(a.y + b.y) / 2}
                fontSize={8}
                fill="var(--ink-faint, #a1a1aa)"
              >
                {(e.stake * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {visibleNodes.map((n) => {
          const p = pos[n.id];
          if (!p) return null;
          const color = riskColor(n.risk, n.is_seed);
          const isSelected = n.id === selectedId;
          const r = n.is_seed ? 14 : n.is_customer ? 12 : 10;
          return (
            <g key={n.id}>
              {isSelected && (
                <circle
                  cx={p.x} cy={p.y}
                  r={r + 5}
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
                opacity={0.9}
                stroke={isSelected ? "var(--accent, #2563eb)" : "white"}
                strokeWidth={isSelected ? 2 : 1}
              />
              {n.hops_from_seed != null && n.hops_from_seed > 0 && n.is_customer && (
                <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize={9} fill="white" fontWeight={700}>
                  {n.hops_from_seed}
                </text>
              )}
              <text
                x={p.x}
                y={p.y + r + 13}
                textAnchor="middle"
                fontSize={9}
                fill={isSelected ? "var(--accent, #2563eb)" : "var(--ink-soft, #3f3f46)"}
                fontWeight={n.is_seed || isSelected ? 600 : 400}
              >
                {n.name.length > 20 ? n.name.slice(0, 18) + "…" : n.name}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-2xs text-ink-muted mt-2">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "#7f1d1d" }} />
          Sanctioned
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-ink" style={{ background: "var(--risk-critical, #b91c1c)" }} />
          Affected customer
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-px w-5 bg-paper-line" style={{ borderTop: "2px solid var(--paper-line)" }} />
          Thicker = larger stake
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-flex items-center justify-center h-4 w-4 rounded-full text-white font-bold"
            style={{ background: "var(--risk-critical, #b91c1c)", fontSize: 8 }}
          >
            2
          </span>
          = hops from flagged entity
        </span>
      </div>
    </ZoomablePanel>
  );
}
