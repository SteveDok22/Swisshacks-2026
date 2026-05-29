"use client";

import { useQuery } from "@tanstack/react-query";
import { casesApi } from "@/lib/api";
import {
  cn,
  timeAgo,
  CASE_TYPE_LABELS,
  JURISDICTION_LABELS,
} from "@/lib/utils";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { RiskScore } from "@/components/ui/RiskScore";
import type { CaseListItem } from "@/types/api";
import { ChevronRight, Inbox } from "lucide-react";

interface CaseQueueProps {
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}

/**
 * The case review queue — primary work surface for a compliance officer.
 *
 * Design: dense rows, risk-sorted, with the score as the visual anchor.
 * Each row is a button (full-row click target) with a hover affordance.
 */
export function CaseQueue({ selectedCaseId, onSelectCase }: CaseQueueProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["cases"],
    queryFn: () => casesApi.list({ page_size: 50 }),
  });

  if (isLoading) {
    return <QueueSkeleton />;
  }

  if (error) {
    return (
      <div className="p-6 text-sm text-risk-critical">
        Failed to load cases. Is the backend running on :8000?
      </div>
    );
  }

  const cases = data?.items ?? [];

  // Sort: highest risk first, then unscored, then by recency
  const sorted = [...cases].sort((a, b) => {
    const sa = a.risk_score ?? -1;
    const sb = b.risk_score ?? -1;
    return sb - sa;
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="h-16 shrink-0 border-b border-paper-line px-6 flex items-center justify-between">
        <div>
          <h1 className="font-semibold text-ink">Case Queue</h1>
          <p className="text-xs text-ink-muted mt-0.5">
            {sorted.length} cases · sorted by risk
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <span className="h-2 w-2 rounded-full bg-risk-low animate-pulse" />
          Live
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-ink-muted">
            <Inbox className="h-8 w-8 mb-2" strokeWidth={1.5} />
            <p className="text-sm">No cases in queue</p>
          </div>
        ) : (
          <ul className="divide-y divide-paper-line">
            {sorted.map((c, i) => (
              <CaseRow
                key={c.id}
                case={c}
                index={i}
                selected={c.id === selectedCaseId}
                onClick={() => onSelectCase(c.id)}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function CaseRow({
  case: c,
  index,
  selected,
  onClick,
}: {
  case: CaseListItem;
  index: number;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        onClick={onClick}
        style={{ animationDelay: `${index * 30}ms` }}
        className={cn(
          "w-full text-left px-6 py-4 flex items-start gap-4 group transition-colors animate-slide-up opacity-0",
          selected ? "bg-accent-bg" : "hover:bg-paper-sunken",
        )}
      >
        {/* Score column */}
        <div className="w-12 shrink-0 pt-0.5">
          <RiskScore score={c.risk_score} level={c.risk_level} size="md" />
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <RiskBadge level={c.risk_level} size="sm" />
            <span className="text-2xs text-ink-muted uppercase tracking-wide">
              {CASE_TYPE_LABELS[c.case_type] ?? c.case_type}
            </span>
          </div>
          <p className="text-sm text-ink leading-snug line-clamp-2">
            {c.summary}
          </p>
          <div className="flex items-center gap-3 mt-1.5 text-2xs text-ink-muted">
            <span>{JURISDICTION_LABELS[c.jurisdiction]?.split(" · ")[1] ?? c.jurisdiction}</span>
            <span>·</span>
            <span>{timeAgo(c.created_at)}</span>
            <span>·</span>
            <span className="capitalize">{c.status.replace("_", " ")}</span>
          </div>
        </div>

        {/* Chevron */}
        <ChevronRight
          className={cn(
            "h-4 w-4 shrink-0 mt-1 transition-colors",
            selected ? "text-accent" : "text-ink-faint group-hover:text-ink-muted",
          )}
        />
      </button>
    </li>
  );
}

function QueueSkeleton() {
  return (
    <div className="flex flex-col h-full">
      <div className="h-16 shrink-0 border-b border-paper-line px-6 flex items-center">
        <div className="h-5 w-32 bg-paper-sunken rounded animate-pulse" />
      </div>
      <div className="divide-y divide-paper-line">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="px-6 py-4 flex items-start gap-4">
            <div className="h-6 w-8 bg-paper-sunken rounded animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-24 bg-paper-sunken rounded animate-pulse" />
              <div className="h-4 w-full bg-paper-sunken rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
