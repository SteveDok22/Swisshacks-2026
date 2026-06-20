"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { driftApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Sidebar } from "@/components/layout/Sidebar";
import { DriftRadar } from "@/components/drift/DriftRadar";
import { DriftTimeline } from "@/components/drift/DriftTimeline";
import { ContagionGraph } from "@/components/drift/ContagionGraph";
import { TwoLayerPanel } from "@/components/drift/TwoLayerPanel";
import { CausalPanel } from "@/components/drift/CausalPanel";
import { StabilityPanel } from "@/components/drift/StabilityPanel";
import { TimeTravelPanel } from "@/components/drift/TimeTravelPanel";
import { DecisionBar } from "@/components/cases/DecisionBar";
import type { DriftCustomerDetail } from "@/types/api";
import { Activity, Zap, DollarSign, FlaskConical, Loader2, ArrowRight, ShieldCheck, ShieldAlert } from "lucide-react";

/**
 * Drift Engine workspace — AMINA Challenge 4.
 *
 * Layout:
 *   [ Sidebar ] [ Radar + Cost meter + Red-team ] [ Timeline + Contagion + Layers ]
 */
export default function DriftPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: customers, isLoading } = useQuery({
    queryKey: ["drift-customers"],
    queryFn: driftApi.customers,
  });

  const { data: detail } = useQuery({
    queryKey: ["drift-customer", selectedId],
    queryFn: () => driftApi.customer(selectedId!),
    enabled: !!selectedId,
  });

  const { data: scan } = useQuery({
    queryKey: ["drift-scan"],
    queryFn: driftApi.scan,
  });

  const { data: contagion } = useQuery({
    queryKey: ["drift-contagion"],
    queryFn: driftApi.contagion,
  });

  const injectMutation = useMutation({
    mutationFn: () => driftApi.inject("combined", "Red Team Phantom"),
    onSuccess: (newCustomer) => {
      queryClient.invalidateQueries({ queryKey: ["drift-customers"] });
      queryClient.invalidateQueries({ queryKey: ["drift-scan"] });
      setSelectedId(newCustomer.drift_id);
    },
  });

  // Auto-select highest-risk customer once loaded
  useEffect(() => {
    if (!selectedId && customers && customers.length > 0) {
      setSelectedId(customers[0].drift_id);
    }
  }, [customers, selectedId]);

  return (
    <div className="flex h-screen overflow-hidden relative z-10">
      <Sidebar />

      {/* Left work column */}
      <div className="w-[560px] shrink-0 border-r border-paper-line bg-paper overflow-y-auto">
        <div className="h-16 border-b border-paper-line px-6 flex items-center justify-between bg-paper-raised">
          <div>
            <h1 className="font-semibold text-ink">Drift Engine</h1>
            <p className="text-xs text-ink-muted mt-0.5">
              KYC drift detection · AMINA Challenge 4
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink-muted">
            <span className="h-2 w-2 rounded-full bg-risk-low animate-pulse" />
            Live
          </div>
        </div>

        <div className="p-4 space-y-4">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-ink-muted p-8 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading book…
            </div>
          ) : (
            <>
              {/* Cost meter */}
              {scan && (
                <div className="border border-paper-line rounded bg-paper-raised p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <DollarSign className="h-3.5 w-3.5 text-risk-low" strokeWidth={2} />
                    <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
                      Cost-Aware Cascade
                    </h3>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-2">
                    <CostStat label="T0 rules" value={scan.tier_counts.T0_RULES ?? 0} sub="free" />
                    <CostStat label="T1 ML" value={scan.tier_counts.T1_ML ?? 0} sub={`$${(scan.tier_costs.T1_ML ?? 0).toFixed(4)}`} />
                    <CostStat label="T2 Claude" value={scan.tier_counts.T2_LLM ?? 0} sub={`$${(scan.tier_costs.T2_LLM ?? 0).toFixed(2)}`} />
                  </div>
                  <div className="flex items-baseline justify-between pt-2 border-t border-paper-line">
                    <span className="text-xs text-ink-soft">
                      Total <span className="font-mono font-semibold text-ink">${scan.total_cost.toFixed(2)}</span>
                      {" vs "}
                      <span className="font-mono text-ink-muted line-through">${scan.llm_on_everything_cost.toFixed(2)}</span>
                    </span>
                    <span className="font-mono text-sm font-semibold text-risk-low tabular">
                      −{scan.savings_pct.toFixed(0)}%
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-2xs text-ink-muted">
                    <span>Actual T2 adjudications</span>
                    <span className="font-mono text-ink-soft tabular">
                      {scan.actual_t2_llm_calls} total · {scan.real_t2_llm_calls} real · {scan.mock_t2_llm_calls} mock
                    </span>
                  </div>
                </div>
              )}

              {/* Radar */}
              {customers && (
                <DriftRadar
                  customers={customers}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              )}

              {/* Red-team button */}
              <button
                onClick={() => injectMutation.mutate()}
                disabled={injectMutation.isPending}
                className="w-full flex items-center justify-center gap-2 border border-paper-line rounded py-2.5 text-sm font-medium text-ink-soft hover:bg-paper-sunken hover:text-ink transition-colors"
              >
                {injectMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FlaskConical className="h-4 w-4" strokeWidth={2} />
                )}
                Red-team: inject synthetic drift scenario
              </button>
            </>
          )}
        </div>
      </div>

      {/* Right detail column */}
      <main className="flex-1 min-w-0 bg-paper overflow-y-auto">
        {detail ? (
          <div className="p-6 space-y-5">
            {/* Customer header */}
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-base font-semibold text-ink">{detail.name}</h2>
                <span
                  className={cn(
                    "text-2xs px-2 py-0.5 rounded font-medium",
                    detail.velocity_band === "rapid" && "bg-risk-critical-bg text-risk-critical",
                    detail.velocity_band === "structural" && "bg-risk-high-bg text-risk-high",
                    detail.velocity_band === "notable" && "bg-risk-medium-bg text-risk-medium",
                    detail.velocity_band === "natural" && "bg-risk-low-bg text-risk-low",
                  )}
                >
                  {detail.velocity_band}
                </span>
                {detail.causal && (
                  <span
                    className={cn(
                      "text-2xs px-2 py-0.5 rounded font-medium",
                      detail.causal.label === "risk" && "bg-risk-critical-bg text-risk-critical",
                      detail.causal.label === "benign" && "bg-risk-low-bg text-risk-low",
                      detail.causal.label === "ambiguous" && "bg-risk-medium-bg text-risk-medium",
                    )}
                  >
                    {detail.causal.label === "benign" ? "✓ benign" : detail.causal.label}
                  </span>
                )}
                {detail.stability?.is_suspicious && (
                  <span className="text-2xs px-2 py-0.5 rounded font-medium bg-risk-high text-white">
                    slow-walker
                  </span>
                )}
                {detail.scenario && (
                  <span className="text-2xs text-ink-faint font-mono">
                    [{detail.scenario}]
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-2xs text-ink-muted">
                <span className="flex items-center gap-1">
                  <Activity className="h-3 w-3" /> Score{" "}
                  <span className="font-mono text-ink">{detail.drift_score}</span>
                </span>
                <span className="flex items-center gap-1">
                  <Zap className="h-3 w-3" /> Velocity{" "}
                  <span className="font-mono text-ink">{detail.drift_velocity}</span>
                </span>
                <span>Tier: <span className="font-mono text-ink">{detail.reached_tier}</span></span>
              </div>
            </div>

            {/* === VERDICT BAR — the one-line "what to do" summary === */}
            <VerdictBar detail={detail} />

            {/* === DECISION BAR — officer records their compliance action === */}
            <DecisionBar
              key={detail.drift_id}
              driftId={detail.drift_id}
              aiRecommendedAction={detail.recommended_action}
            />

            {/* === Two-column analysis grid (was a long vertical scroll) === */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
              {/* Left column: what is happening */}
              <div className="space-y-5">
                {detail.causal && <CausalPanel causal={detail.causal} />}
                <DriftTimeline detail={detail} />
                <TwoLayerPanel detail={detail} />
              </div>

              {/* Right column: evidence & context */}
              <div className="space-y-5">
                {detail.stability && <StabilityPanel stability={detail.stability} />}
                <TimeTravelPanel driftId={detail.drift_id} />

                {/* Signal Layers */}
                <div className="border border-paper-line rounded bg-paper-raised p-4">
                  <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-3">
                    Signal Layers
                  </h3>
                  <div className="space-y-2">
                    {detail.layers.map((l) => (
                      <div key={l.layer} className="flex items-start gap-3 py-1.5 border-b border-paper-line/50 last:border-0">
                        <span className="font-mono text-2xs text-ink-faint w-5 shrink-0">L{l.layer}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs text-ink font-medium">{l.name}</span>
                            <span className="font-mono text-2xs tabular text-ink-soft">
                              LLR {l.llr.toFixed(2)}
                            </span>
                          </div>
                          {l.detail && (
                            <p className="text-2xs text-ink-muted mt-0.5">{l.detail}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {contagion && <ContagionGraph data={contagion} />}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-ink-muted text-sm">
            Select a customer from the radar
          </div>
        )}
      </main>
    </div>
  );
}

function VerdictBar({ detail }: { detail: DriftCustomerDetail }) {
  // Derive a single recommended action from the full picture.
  const score = detail.drift_score;
  const causal = detail.causal?.label ?? "ambiguous";
  const suspicious = detail.stability?.is_suspicious ?? false;

  let action: string;
  let tone: "critical" | "high" | "medium" | "low";
  let Icon = ShieldAlert;

  if (suspicious) {
    action = "Escalate — suspicious stability (possible slow-walker)";
    tone = "high";
  } else if (causal === "benign") {
    action = "Monitor only — change matches legitimate business growth";
    tone = "low";
    Icon = ShieldCheck;
  } else if (score >= 70 || causal === "risk") {
    action = "Escalate to enhanced due diligence — risk-shaped drift";
    tone = "critical";
  } else if (score >= 40 || causal === "ambiguous") {
    action = "Request information — ambiguous, needs human review";
    tone = "medium";
  } else {
    action = "No action — within normal range";
    tone = "low";
    Icon = ShieldCheck;
  }

  const toneClasses = {
    critical: "border-risk-critical/25 bg-risk-critical-bg text-risk-critical",
    high: "border-risk-high/25 bg-risk-high-bg text-risk-high",
    medium: "border-risk-medium/25 bg-risk-medium-bg text-risk-medium",
    low: "border-risk-low/25 bg-risk-low-bg text-risk-low",
  }[tone];

  return (
    <div className={cn("flex items-center gap-3 rounded border p-3", toneClasses)}>
      <Icon className="h-5 w-5 shrink-0" strokeWidth={2} />
      <div className="flex-1 min-w-0">
        <div className="text-2xs uppercase tracking-wide opacity-70">Recommended action</div>
        <div className="text-sm font-semibold">{action}</div>
      </div>
      <div className="flex items-center gap-2 text-2xs shrink-0">
        <span className="font-mono font-semibold text-base tabular">{Math.round(score)}</span>
        <ArrowRight className="h-3.5 w-3.5 opacity-50" />
        <span className="font-mono uppercase">{detail.reached_tier.replace("_", " ")}</span>
      </div>
    </div>
  );
}

function CostStat({ label, value, sub }: { label: string; value: number; sub: string }) {
  return (
    <div className="text-center">
      <div className="font-mono text-lg font-semibold text-ink tabular">{value}</div>
      <div className="text-2xs text-ink-muted">{label}</div>
      <div className="text-2xs text-ink-faint font-mono">{sub}</div>
    </div>
  );
}
