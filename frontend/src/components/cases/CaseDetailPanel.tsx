"use client";

import { useQuery } from "@tanstack/react-query";
import { casesApi } from "@/lib/api";
import {
  CASE_TYPE_LABELS,
  JURISDICTION_LABELS,
  formatDateTime,
} from "@/lib/utils";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { RiskScore } from "@/components/ui/RiskScore";
import { MousePointerClick } from "lucide-react";

interface CaseDetailPanelProps {
  caseId: string | null;
}

/**
 * Right-side detail panel.
 *
 * Day 7: shows basic case context + raw data.
 * Day 8 will add: SHAP viewer, counterfactuals, streaming explanation,
 * anonymization preview, jurisdiction comparison, decision flow.
 */
export function CaseDetailPanel({ caseId }: CaseDetailPanelProps) {
  const { data: caseDetail, isLoading } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.get(caseId!),
    enabled: !!caseId,
  });

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
      <div className="p-6 space-y-4">
        <div className="h-8 w-3/4 bg-paper-sunken rounded animate-pulse" />
        <div className="h-24 w-full bg-paper-sunken rounded animate-pulse" />
      </div>
    );
  }

  const data = caseDetail.context.data;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-paper-line px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <RiskBadge level={caseDetail.risk_level} />
              <span className="text-2xs text-ink-muted uppercase tracking-wide">
                {CASE_TYPE_LABELS[caseDetail.case_type]}
              </span>
            </div>
            <h2 className="text-sm font-medium text-ink leading-snug">
              {caseDetail.context.summary}
            </h2>
          </div>
          {caseDetail.risk_score !== null && (
            <div className="text-right shrink-0">
              <RiskScore
                score={caseDetail.risk_score}
                level={caseDetail.risk_level}
                size="lg"
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-4 mt-4 text-2xs text-ink-muted">
          <span>{JURISDICTION_LABELS[caseDetail.jurisdiction]}</span>
          <span>·</span>
          <span>Created {formatDateTime(caseDetail.created_at)}</span>
          {caseDetail.confidence !== null && (
            <>
              <span>·</span>
              <span>Confidence {(caseDetail.confidence * 100).toFixed(0)}%</span>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
        {/* Case data */}
        <section>
          <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-3">
            Case Details
          </h3>
          <dl className="space-y-2">
            {Object.entries(data).map(([key, value]) => (
              <div
                key={key}
                className="flex items-start justify-between gap-4 py-1.5 border-b border-paper-line/60 last:border-0"
              >
                <dt className="text-xs text-ink-muted capitalize shrink-0">
                  {key.replace(/_/g, " ")}
                </dt>
                <dd className="text-xs text-ink text-right font-mono break-all">
                  {typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Placeholder for Day 8 features */}
        <section className="rounded border border-dashed border-paper-line p-4 text-center">
          <p className="text-xs text-ink-muted">
            SHAP analysis · Counterfactuals · AI explanation
          </p>
          <p className="text-2xs text-ink-faint mt-1">Coming in Day 8</p>
        </section>
      </div>
    </div>
  );
}
