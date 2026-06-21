"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { driftApi } from "@/lib/api";
import { cn, TIER_LABELS, ACTION_LABELS, llrWeight } from "@/lib/utils";
import { Sidebar } from "@/components/layout/Sidebar";
import { DriftRadar } from "@/components/drift/DriftRadar";
import { DriftTimeline } from "@/components/drift/DriftTimeline";
import { ContagionGraph } from "@/components/drift/ContagionGraph";
import { TwoLayerPanel } from "@/components/drift/TwoLayerPanel";
import { WebsiteDiffPanel } from "@/components/drift/WebsiteDiffPanel";
import { UboScreeningPanel } from "@/components/drift/UboScreeningPanel";
import { CausalPanel } from "@/components/drift/CausalPanel";
import { StabilityPanel } from "@/components/drift/StabilityPanel";
import { DormancyPanel } from "@/components/drift/DormancyPanel";
import { TimeTravelPanel } from "@/components/drift/TimeTravelPanel";
import { DecisionBar } from "@/components/cases/DecisionBar";
import type { DriftCustomerDetail } from "@/types/api";
import { DollarSign, FlaskConical, Loader2, ShieldCheck, ShieldAlert, ShieldQuestion, ChevronDown } from "lucide-react";
import { DemoModeBadge } from "@/components/DemoModeBadge";

/**
 * Drift Engine workspace — AMINA Challenge 4.
 *
 * The selected customer lives in the URL (`/drift/<drift_id>`) so a case can
 * be deep-linked and cross-referenced against the audit trail by id.
 *
 * Layout:
 *   [ Sidebar ] [ Radar + Cost meter + Red-team ] [ Timeline + Contagion + Layers ]
 */
export function DriftWorkspace() {
  const params = useParams<{ driftId?: string }>();
  const router = useRouter();
  const selectedId = params.driftId ?? null;
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
      router.push(`/drift/${newCustomer.drift_id}`);
    },
  });

  // Land on /drift with no id → select the highest-risk customer and reflect
  // it in the URL (replace, so the empty index isn't kept in history).
  useEffect(() => {
    if (!selectedId && customers && customers.length > 0) {
      router.replace(`/drift/${customers[0].drift_id}`);
    }
  }, [customers, selectedId, router]);

  return (
    <div className="flex h-screen overflow-hidden relative z-10">
      <DemoModeBadge />
      <Sidebar />

      {/* Left work column */}
      <div className="w-[560px] shrink-0 border-r border-paper-line bg-paper overflow-y-auto">
        <div className="h-16 border-b border-paper-line px-6 flex items-center justify-between bg-paper-raised">
          <div>
            <h1 className="font-semibold text-ink">Drift Engine</h1>
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
                    <CostStat label="T2 LLM" value={scan.tier_counts.T2_LLM ?? 0} sub={`$${(scan.tier_costs.T2_LLM ?? 0).toFixed(2)}`} />
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
                </div>
              )}

              {/* Radar */}
              {customers && (
                <DriftRadar
                  customers={customers}
                  selectedId={selectedId}
                  onSelect={(id) => router.push(`/drift/${id}`)}
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
            {/* Case summary — identity + authoritative verdict + KPIs, one block */}
            <CaseSummary detail={detail} />

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
                <WebsiteDiffPanel detail={detail} />
                <UboScreeningPanel hits={detail.ubo_screening} />
              </div>

              {/* Right column: evidence & context */}
              <div className="space-y-5">
                {detail.stability && <StabilityPanel stability={detail.stability} />}
                {detail.dormancy && <DormancyPanel dormancy={detail.dormancy} />}
                <TimeTravelPanel driftId={detail.drift_id} />

                {/* Signal Layers */}
                <details className="group border border-paper-line rounded bg-paper-raised">
                  <summary className="flex items-center justify-between gap-2 px-4 py-3 cursor-pointer list-none select-none">
                    <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
                      Signal Layers
                      <span className="ml-2 font-normal normal-case tracking-normal text-ink-faint">
                        technical breakdown
                      </span>
                    </h3>
                    <ChevronDown className="h-4 w-4 text-ink-faint transition-transform group-open:rotate-180" strokeWidth={2} />
                  </summary>
                  <div className="px-4 pb-4 space-y-2">
                    {detail.layers.map((l) => {
                      const w = llrWeight(l.llr);
                      return (
                        <div
                          key={l.layer}
                          className="flex items-start gap-3 py-1.5 border-b border-paper-line/50 last:border-0"
                          title={`Log-likelihood ratio: ${l.llr.toFixed(2)} · status: ${l.status}`}
                        >
                          <span className="font-mono text-2xs text-ink-faint w-5 shrink-0">L{l.layer}</span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs text-ink font-medium">{l.name}</span>
                              <span className={cn("text-2xs font-medium shrink-0", w.color)}>
                                {w.label}
                              </span>
                            </div>
                            {l.detail && (
                              <p className="text-2xs text-ink-muted mt-0.5">{l.detail}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </details>

                {contagion && <ContagionGraph data={contagion} selectedId={selectedId} />}
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

function CaseSummary({ detail }: { detail: DriftCustomerDetail }) {
  const score = detail.drift_score;
  const action = detail.recommended_action;
  const reasons = detail.escalation_reasons ?? [];

  // Tone follows the backend risk level; the action label follows the backend
  // recommendation — the same value the Decision Bar highlights, so the two
  // surfaces can never disagree.
  const toneClasses = {
    critical: "bg-risk-critical-bg text-risk-critical",
    high: "bg-risk-high-bg text-risk-high",
    medium: "bg-risk-medium-bg text-risk-medium",
    low: "bg-risk-low-bg text-risk-low",
  }[detail.risk_level];

  const Icon =
    action === "allow"
      ? ShieldCheck
      : action === "step_up_verification"
        ? ShieldQuestion
        : ShieldAlert;

  // One-line driver — what made this the recommendation. Prioritised so the
  // exceptional detectors always surface, then the causal verdict.
  const driver = (() => {
    if (detail.dormancy?.is_dormancy_break)
      return "Dormancy break — sudden activation after a quiet baseline";
    if (detail.stability?.is_suspicious)
      return "Suspicious stability — anomalously smooth while peers move";
    switch (detail.causal?.label) {
      case "risk":
        return "Risk-shaped drift — margin signature points to transit";
      case "benign":
        return "Legitimate growth pattern — routine monitoring";
      case "ambiguous":
        return "Inconclusive signal — needs human review";
      default:
        return "Within expected range";
    }
  })();

  const bandClasses = cn(
    detail.velocity_band === "rapid" && "bg-risk-critical-bg text-risk-critical",
    detail.velocity_band === "structural" && "bg-risk-high-bg text-risk-high",
    detail.velocity_band === "notable" && "bg-risk-medium-bg text-risk-medium",
    detail.velocity_band === "natural" && "bg-risk-low-bg text-risk-low",
  );

  return (
    <div className="space-y-3">
      {/* Identity line */}
      <div className="flex items-center gap-2 flex-wrap">
        <h2 className="text-base font-semibold text-ink">{detail.name}</h2>
        <span className="font-mono text-2xs text-ink-muted bg-paper-sunken rounded px-1.5 py-0.5">
          {detail.drift_id}
        </span>
        <span className={cn("text-2xs px-2 py-0.5 rounded font-medium capitalize", bandClasses)}>
          {detail.velocity_band} drift
        </span>
        {detail.scenario && (
          <span className="text-2xs text-ink-faint">
            {detail.scenario.replace(/_/g, " ")}
          </span>
        )}
      </div>

      {/* Verdict banner — single authoritative "what to do + why + KPIs" */}
      <div className={cn("flex items-center gap-3 rounded p-3", toneClasses)}>
        <Icon className="h-5 w-5 shrink-0" strokeWidth={2} />
        <div className="flex-1 min-w-0">
          <div className="text-2xs uppercase tracking-wide opacity-70">
            Recommended action
          </div>
          <div className="text-sm font-semibold">{ACTION_LABELS[action] ?? action}</div>
          <div className="text-2xs opacity-80">{driver}</div>
          {reasons.length > 0 && (
            <div className="text-2xs text-ink-muted mt-1">
              Routing: {reasons.join(" · ")}
            </div>
          )}
        </div>
        <div className="flex items-stretch gap-4 shrink-0 text-center">
          <div className="flex flex-col justify-center">
            <div className="font-mono text-2xl font-semibold tabular leading-none">
              {Math.round(score)}
              <span className="text-sm opacity-50"> / 100</span>
            </div>
          </div>
          <div className="border-l border-black/10 pl-4 flex flex-col justify-center">
            <div className="text-sm font-semibold leading-none">
              {TIER_LABELS[detail.reached_tier] ?? detail.reached_tier}
            </div>
            <div className="text-2xs opacity-50 mt-1">reviewed by</div>
          </div>
        </div>
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
