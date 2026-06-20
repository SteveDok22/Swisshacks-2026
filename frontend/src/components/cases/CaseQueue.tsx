"use client";

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { casesApi, scoringApi, ApiError } from "@/lib/api";
import {
  cn,
  timeAgo,
  CASE_TYPE_LABELS,
  JURISDICTION_LABELS,
} from "@/lib/utils";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { RiskScore } from "@/components/ui/RiskScore";
import type { CaseListItem, PaginatedResponse } from "@/types/api";
import { ChevronRight, Inbox, AlertCircle, RefreshCw } from "lucide-react";

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
  const queryClient = useQueryClient();
  const scoringIdsRef = useRef<Set<string>>(new Set());
  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ["cases"],
    queryFn: () => casesApi.list({ page_size: 50 }),
  });

  useEffect(() => {
    const unscored = (data?.items ?? []).filter(
      (c) => c.risk_score === null && !scoringIdsRef.current.has(c.id),
    );
    if (unscored.length === 0) return;

    unscored.forEach((c) => scoringIdsRef.current.add(c.id));
    let cancelled = false;

    Promise.allSettled(unscored.map((c) => scoringApi.score(c.id))).then(
      (results) => {
        if (cancelled) return;

        const scoredById = new Map<
          string,
          { score: number; level: CaseListItem["risk_level"] }
        >();
        results.forEach((result, index) => {
          if (result.status !== "fulfilled") return;
          scoredById.set(unscored[index].id, {
            score: result.value.result.score,
            level: result.value.result.level,
          });
        });

        if (scoredById.size > 0) {
          queryClient.setQueryData<PaginatedResponse<CaseListItem>>(
            ["cases"],
            (old) =>
              old
                ? {
                    ...old,
                    items: old.items.map((item) => {
                      const scored = scoredById.get(item.id);
                      return scored
                        ? {
                            ...item,
                            risk_score: scored.score,
                            risk_level: scored.level,
                          }
                        : item;
                    }),
                  }
                : old,
          );
        }

        queryClient.invalidateQueries({ queryKey: ["cases"] });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [data?.items, queryClient]);

  if (isLoading) {
    return <QueueSkeleton />;
  }

  if (error) {
    const isNetwork =
      !(error instanceof ApiError) ||
      error.message.includes("timed out") ||
      error.message.includes("Failed to fetch");
    return (
      <div className="flex flex-col h-full">
        <div className="h-16 shrink-0 border-b border-paper-line px-6 flex items-center">
          <h1 className="font-semibold text-ink">Case Queue</h1>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-sm text-center">
            <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-risk-medium-bg mb-3">
              <AlertCircle
                className="h-5 w-5 text-risk-medium"
                strokeWidth={2}
              />
            </div>
            <h3 className="text-sm font-semibold text-ink mb-1.5">
              {isNetwork ? "Can't reach the backend" : "Failed to load cases"}
            </h3>
            <p className="text-xs text-ink-muted leading-relaxed mb-4">
              {isNetwork
                ? "Make sure the backend is running on http://localhost:8000"
                : `Error: ${error.message}`}
            </p>
            <button
              onClick={() => refetch()}
              disabled={isRefetching}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent text-paper-raised text-xs font-medium hover:bg-accent-soft transition-colors disabled:opacity-60"
            >
              <RefreshCw
                className={cn(
                  "h-3 w-3",
                  isRefetching && "animate-spin",
                )}
                strokeWidth={2.5}
              />
              {isRefetching ? "Retrying…" : "Try again"}
            </button>
          </div>
        </div>
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
