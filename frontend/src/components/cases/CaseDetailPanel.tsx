"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { casesApi, scoringApi } from "@/lib/api";
import {
  CASE_TYPE_LABELS,
  JURISDICTION_LABELS,
  formatDateTime,
} from "@/lib/utils";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { RiskScore } from "@/components/ui/RiskScore";
import { SHAPViewer } from "@/components/cases/SHAPViewer";
import { StreamingExplanation } from "@/components/cases/StreamingExplanation";
import { CounterfactualsViewer } from "@/components/cases/CounterfactualsViewer";
import { PrivacyPanel } from "@/components/cases/PrivacyPanel";
import { JurisdictionSelector } from "@/components/cases/JurisdictionSelector";
import { DecisionBar } from "@/components/cases/DecisionBar";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import {
  SHAPSkeleton,
  CounterfactualsSkeleton,
  JurisdictionSkeleton,
  StreamingSkeleton,
} from "@/components/ui/Skeleton";
import { MousePointerClick, Activity } from "lucide-react";
import type {
  CaseDetail,
  CaseListItem,
  Jurisdiction,
  PaginatedResponse,
} from "@/types/api";

interface CaseDetailPanelProps {
  caseId: string | null;
}

/**
 * Complete case review surface.
 *
 * Single-page scroll narrative:
 *   1. Header — score + summary
 *   2. Streaming AI Assessment — live text generation
 *   3. SHAP feature contributions
 *   4. Counterfactual scenarios (high/critical only)
 *   5. Privacy panel — what goes to AI
 *   6. Jurisdiction comparison toggle
 *
 * Sticky bottom: Decision bar (Allow / Step-up / Escalate / Block).
 *
 * This is what gets demoed.
 */
export function CaseDetailPanel({ caseId }: CaseDetailPanelProps) {
  const queryClient = useQueryClient();
  const [activeJurisdiction, setActiveJurisdiction] =
    useState<Jurisdiction>("CH");

  const { data: caseDetail, isLoading } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.get(caseId!),
    enabled: !!caseId,
  });

  // Sync active jurisdiction with case's jurisdiction
  useEffect(() => {
    if (caseDetail) {
      setActiveJurisdiction(caseDetail.jurisdiction);
    }
  }, [caseDetail]);

  // Get top features either from scoring result or refetch via score endpoint
  const { data: scoring } = useQuery({
    queryKey: ["scoring", caseId],
    queryFn: () => scoringApi.score(caseId!),
    enabled: !!caseId && !!caseDetail,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!caseId || !scoring) return;

    const { score, level, confidence, scored_at } = scoring.result;

    queryClient.setQueryData<CaseDetail>(["case", caseId], (old) =>
      old
        ? {
            ...old,
            risk_score: score,
            risk_level: level,
            confidence,
            scored_at,
          }
        : old,
    );
    queryClient.setQueryData<PaginatedResponse<CaseListItem>>(
      ["cases"],
      (old) =>
        old
          ? {
              ...old,
              items: old.items.map((item) =>
                item.id === caseId
                  ? { ...item, risk_score: score, risk_level: level }
                  : item,
              ),
            }
          : old,
    );
  }, [caseId, scoring, queryClient]);

  if (!caseId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-ink-muted">
        <MousePointerClick className="h-8 w-8 mb-3" strokeWidth={1.5} />
        <p className="text-sm">Select a case to review</p>
      </div>
    );
  }

  if (isLoading || !caseDetail) {
    return (
      <div className="p-6 space-y-6">
        <div className="space-y-3">
          <div className="h-5 w-24 bg-paper-sunken rounded animate-pulse" />
          <div className="h-4 w-3/4 bg-paper-sunken rounded animate-pulse" />
          <div className="h-3 w-1/2 bg-paper-sunken rounded animate-pulse" />
        </div>
        <StreamingSkeleton />
        <SHAPSkeleton />
        <JurisdictionSkeleton />
      </div>
    );
  }

  const effectiveScore = scoring?.result.score ?? caseDetail.risk_score;
  const effectiveLevel = scoring?.result.level ?? caseDetail.risk_level;
  const effectiveConfidence =
    scoring?.result.confidence ?? caseDetail.confidence;
  const recommendedAction = scoring?.result.recommended_action ?? null;
  const topFeatures = scoring?.result.top_features ?? [];

  return (
    <div className="flex flex-col h-full">
      {/* === Header === */}
      <div className="shrink-0 border-b border-paper-line px-6 py-5 bg-paper-raised">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <RiskBadge level={effectiveLevel} />
              <span className="text-2xs text-ink-muted uppercase tracking-wide">
                {CASE_TYPE_LABELS[caseDetail.case_type]}
              </span>
            </div>
            <h2 className="text-sm font-medium text-ink leading-snug">
              {caseDetail.context.summary}
            </h2>
            <div className="flex items-center gap-3 mt-3 text-2xs text-ink-muted">
              <span>{JURISDICTION_LABELS[caseDetail.jurisdiction]}</span>
              <span>·</span>
              <span>Created {formatDateTime(caseDetail.created_at)}</span>
              {effectiveConfidence !== null && (
                <>
                  <span>·</span>
                  <span>
                    Confidence {(effectiveConfidence * 100).toFixed(0)}%
                  </span>
                </>
              )}
            </div>
          </div>
          {effectiveScore !== null && (
            <div className="text-right shrink-0">
              <RiskScore
                score={effectiveScore}
                level={effectiveLevel}
                size="lg"
              />
            </div>
          )}
        </div>
      </div>

      {/* === Body — scrollable === */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
        {/* AI Assessment (streaming) */}
        <ErrorBoundary section="AI Assessment">
          <StreamingExplanation caseId={caseId} />
        </ErrorBoundary>

        {/* SHAP */}
        <ErrorBoundary section="Risk Factors">
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Activity
                className="h-3.5 w-3.5 text-ink-muted"
                strokeWidth={2}
              />
              <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
                Risk Factors
              </h3>
              <span className="text-2xs text-ink-faint">
                · top 5 SHAP contributions
              </span>
            </div>
            {topFeatures.length > 0 ? (
              <SHAPViewer features={topFeatures} />
            ) : (
              <SHAPSkeleton />
            )}
          </section>
        </ErrorBoundary>

        {/* Counterfactuals (high/critical only) */}
        {(effectiveLevel === "high" || effectiveLevel === "critical") && (
          <ErrorBoundary section="Alternative Scenarios">
            <CounterfactualsViewer caseId={caseId} />
          </ErrorBoundary>
        )}

        {/* Jurisdiction comparison */}
        <ErrorBoundary section="Jurisdiction Comparison">
          <JurisdictionSelector
            caseId={caseId}
            current={activeJurisdiction}
            onSelect={setActiveJurisdiction}
          />
        </ErrorBoundary>

        {/* Privacy */}
        <ErrorBoundary section="Data Handling">
          <PrivacyPanel caseId={caseId} />
        </ErrorBoundary>

        {/* Case raw data — at the bottom, collapsed by default */}
        <details className="border border-paper-line rounded">
          <summary className="px-3 py-2 cursor-pointer text-2xs font-semibold uppercase tracking-wide text-ink-muted hover:text-ink">
            Raw Case Data
          </summary>
          <dl className="px-3 pb-3 space-y-1.5">
            {Object.entries(caseDetail.context.data).map(([key, value]) => (
              <div
                key={key}
                className="flex items-start justify-between gap-3 py-1 border-b border-paper-line/40 last:border-0"
              >
                <dt className="text-2xs text-ink-muted capitalize shrink-0">
                  {key.replace(/_/g, " ")}
                </dt>
                <dd className="text-2xs text-ink text-right font-mono break-all max-w-[60%]">
                  {typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      </div>

      {/* === Decision bar (sticky) === */}
      <DecisionBar
        key={caseId}
        caseId={caseId}
        aiRecommendedAction={recommendedAction}
      />
    </div>
  );
}
