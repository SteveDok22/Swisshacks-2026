"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/lib/api";
import { cn, riskColors, formatDateTime } from "@/lib/utils";
import { Sidebar } from "@/components/layout/Sidebar";
import { RiskBadge } from "@/components/ui/RiskBadge";
import type { AuditEntry, RiskLevel } from "@/types/api";
import {
  FileSearch,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  ChevronLeft,
  ChevronRight as ChevronRightNav,
  Filter,
  X,
} from "lucide-react";

// === Event type metadata ===

type EventCategory = "case" | "drift" | "decision" | "export" | "other";

const EVENT_META: Record<
  string,
  { label: string; category: EventCategory }
> = {
  case_created:               { label: "Case Created",             category: "case" },
  case_scored:                { label: "Case Scored",              category: "case" },
  explanation_generated:      { label: "Explanation Generated",    category: "case" },
  decision_recorded:          { label: "Decision Recorded",        category: "decision" },
  counterfactuals_generated:  { label: "Counterfactuals",          category: "case" },
  jurisdiction_compared:      { label: "Jurisdiction Compared",    category: "case" },
  data_exported:              { label: "Data Exported",            category: "export" },
  drift_customer_analyzed:    { label: "Drift Analyzed",           category: "drift" },
  drift_scan_completed:       { label: "Drift Scan",               category: "drift" },
  drift_replay_executed:      { label: "Replay Executed",          category: "drift" },
  drift_scenario_injected:    { label: "Scenario Injected",        category: "drift" },
  drift_rfi_generated:        { label: "RFI Generated",            category: "drift" },
};

const CATEGORY_CLASSES: Record<EventCategory, string> = {
  case:     "bg-accent-bg text-accent border border-accent/20",
  drift:    "bg-purple-50 text-purple-700 border border-purple-200",
  decision: "bg-amber-50 text-amber-700 border border-amber-200",
  export:   "bg-orange-50 text-orange-700 border border-orange-200",
  other:    "bg-paper-sunken text-ink-soft border border-paper-line",
};

function EventTypeBadge({ eventType }: { eventType: string }) {
  const meta = EVENT_META[eventType];
  const label = meta?.label ?? eventType.replace(/_/g, " ");
  const cat = meta?.category ?? "other";
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 rounded-sm text-2xs font-medium whitespace-nowrap",
        CATEGORY_CLASSES[cat],
      )}
    >
      {label}
    </span>
  );
}

// === Payload viewer ===

function PayloadRow({ entry }: { entry: AuditEntry }) {
  const [open, setOpen] = useState(false);
  const hasPayload = Object.keys(entry.payload).length > 0;

  return (
    <>
      <tr
        className={cn(
          "border-b border-paper-line transition-colors",
          open ? "bg-accent-bg/30" : "hover:bg-paper-sunken/60",
          hasPayload && "cursor-pointer",
        )}
        onClick={() => hasPayload && setOpen((v) => !v)}
      >
        <td className="px-3 py-2.5 w-5 text-ink-faint">
          {hasPayload ? (
            open ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )
          ) : null}
        </td>
        <td className="px-3 py-2.5 font-mono text-2xs text-ink-muted whitespace-nowrap">
          {formatDateTime(entry.occurred_at)}
        </td>
        <td className="px-3 py-2.5">
          <EventTypeBadge eventType={entry.event_type} />
        </td>
        <td className="px-3 py-2.5 text-xs text-ink-soft">
          {entry.actor_id ?? <span className="text-ink-faint">—</span>}
          {entry.actor_type && entry.actor_type !== "system" && (
            <span className="ml-1 text-2xs text-ink-faint">
              ({entry.actor_type})
            </span>
          )}
        </td>
        <td className="px-3 py-2.5 font-mono text-2xs text-ink-muted">
          {entry.case_id ? (
            <span title={entry.case_id}>{entry.case_id.slice(0, 8)}…</span>
          ) : (
            <span className="text-ink-faint">—</span>
          )}
        </td>
        <td className="px-3 py-2.5 font-mono text-2xs text-ink-muted">
          {entry.client_id ? (
            <span title={entry.client_id}>{entry.client_id.slice(0, 8)}…</span>
          ) : (
            <span className="text-ink-faint">—</span>
          )}
        </td>
        <td className="px-3 py-2.5">
          {entry.risk_level ? (
            <RiskBadge level={entry.risk_level as RiskLevel} size="sm" />
          ) : (
            <span className="text-ink-faint text-2xs">—</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-2xs text-ink-muted tabular-nums">
          {entry.risk_score != null ? entry.risk_score.toFixed(1) : "—"}
        </td>
      </tr>
      {open && hasPayload && (
        <tr className="border-b border-paper-line bg-paper-sunken/40">
          <td />
          <td colSpan={7} className="px-4 pb-3 pt-2">
            <pre className="text-2xs font-mono text-ink-soft leading-relaxed overflow-x-auto whitespace-pre-wrap break-words max-h-48">
              {JSON.stringify(entry.payload, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

// === Filter bar ===

const EVENT_TYPE_OPTIONS = [
  { value: "", label: "All event types" },
  { value: "case_created", label: "Case Created" },
  { value: "case_scored", label: "Case Scored" },
  { value: "explanation_generated", label: "Explanation Generated" },
  { value: "decision_recorded", label: "Decision Recorded" },
  { value: "counterfactuals_generated", label: "Counterfactuals" },
  { value: "jurisdiction_compared", label: "Jurisdiction Compared" },
  { value: "data_exported", label: "Data Exported" },
  { value: "drift_customer_analyzed", label: "Drift Analyzed" },
  { value: "drift_scan_completed", label: "Drift Scan" },
  { value: "drift_replay_executed", label: "Replay Executed" },
  { value: "drift_scenario_injected", label: "Scenario Injected" },
  { value: "drift_rfi_generated", label: "RFI Generated" },
];

const RISK_LEVEL_OPTIONS = [
  { value: "", label: "All risk levels" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

interface Filters {
  event_type: string;
  risk_level: string;
  actor_id: string;
  from_date: string;
  to_date: string;
}

const DEFAULT_FILTERS: Filters = {
  event_type: "",
  risk_level: "",
  actor_id: "",
  from_date: "",
  to_date: "",
};

function hasActiveFilters(f: Filters) {
  return Object.values(f).some((v) => v !== "");
}

// === Main page ===

export default function AuditLogPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  const { data, isLoading, isFetching, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["audit", appliedFilters, page],
    queryFn: () =>
      auditApi.search({
        event_type: appliedFilters.event_type || undefined,
        risk_level: appliedFilters.risk_level || undefined,
        actor_id: appliedFilters.actor_id || undefined,
        from_date: appliedFilters.from_date || undefined,
        to_date: appliedFilters.to_date || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    staleTime: 30_000,
  });

  const applyFilters = useCallback(() => {
    setAppliedFilters(filters);
    setPage(1);
  }, [filters]);

  const clearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setAppliedFilters(DEFAULT_FILTERS);
    setPage(1);
  }, []);

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  return (
    <div className="flex h-screen overflow-hidden relative z-10">
      <Sidebar />

      <div className="flex-1 min-w-0 flex flex-col bg-paper overflow-hidden">
        {/* Header */}
        <div className="h-16 border-b border-paper-line px-6 flex items-center justify-between bg-paper-raised shrink-0">
          <div className="flex items-center gap-3">
            <FileSearch className="h-5 w-5 text-accent" strokeWidth={2} />
            <div>
              <h1 className="font-semibold text-ink">Audit Log</h1>
              <p className="text-xs text-ink-muted mt-0.5">
                Immutable compliance trail · FINMA Article 9 · append-only
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {data && (
              <span className="text-xs text-ink-muted">
                {data.total.toLocaleString()} event{data.total !== 1 ? "s" : ""}
                {lastUpdated && (
                  <span className="ml-2 text-ink-faint">
                    · updated {lastUpdated}
                  </span>
                )}
              </span>
            )}
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium border border-paper-line",
                "text-ink-soft hover:bg-paper-sunken hover:text-ink transition-colors",
                isFetching && "opacity-50 cursor-not-allowed",
              )}
            >
              <RefreshCw
                className={cn("h-3.5 w-3.5", isFetching && "animate-spin")}
              />
              Refresh
            </button>
          </div>
        </div>

        {/* Filter bar */}
        <div className="shrink-0 border-b border-paper-line bg-paper-raised px-6 py-3">
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 text-xs text-ink-muted font-medium mt-0.5 shrink-0">
              <Filter className="h-3.5 w-3.5" />
              Filters
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="text-2xs text-ink-faint font-medium">Event type</label>
              <select
                value={filters.event_type}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, event_type: e.target.value }))
                }
                className="h-8 rounded border border-paper-line bg-paper text-xs text-ink px-2 pr-6 min-w-[160px] focus:outline-none focus:ring-1 focus:ring-accent/30"
              >
                {EVENT_TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="text-2xs text-ink-faint font-medium">Risk level</label>
              <select
                value={filters.risk_level}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, risk_level: e.target.value }))
                }
                className="h-8 rounded border border-paper-line bg-paper text-xs text-ink px-2 pr-6 min-w-[120px] focus:outline-none focus:ring-1 focus:ring-accent/30"
              >
                {RISK_LEVEL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="text-2xs text-ink-faint font-medium">Actor ID</label>
              <input
                type="text"
                placeholder="e.g. anna.mueller"
                value={filters.actor_id}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, actor_id: e.target.value }))
                }
                className="h-8 rounded border border-paper-line bg-paper text-xs text-ink px-2 min-w-[140px] placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent/30"
              />
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="text-2xs text-ink-faint font-medium">From</label>
              <input
                type="datetime-local"
                value={filters.from_date}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, from_date: e.target.value }))
                }
                className="h-8 rounded border border-paper-line bg-paper text-xs text-ink px-2 focus:outline-none focus:ring-1 focus:ring-accent/30"
              />
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="text-2xs text-ink-faint font-medium">To</label>
              <input
                type="datetime-local"
                value={filters.to_date}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, to_date: e.target.value }))
                }
                className="h-8 rounded border border-paper-line bg-paper text-xs text-ink px-2 focus:outline-none focus:ring-1 focus:ring-accent/30"
              />
            </div>

            <div className="flex items-end gap-2">
              <button
                onClick={applyFilters}
                className="h-8 px-3 rounded bg-accent text-paper-raised text-xs font-medium hover:bg-accent-soft transition-colors"
              >
                Apply
              </button>
              {hasActiveFilters(appliedFilters) && (
                <button
                  onClick={clearFilters}
                  className="h-8 px-2.5 rounded border border-paper-line text-xs text-ink-muted hover:bg-paper-sunken hover:text-ink transition-colors flex items-center gap-1"
                >
                  <X className="h-3.5 w-3.5" />
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Active filter chips */}
          {hasActiveFilters(appliedFilters) && (
            <div className="flex items-center gap-1.5 mt-2.5 flex-wrap">
              <span className="text-2xs text-ink-faint">Active:</span>
              {appliedFilters.event_type && (
                <Chip label={`type: ${appliedFilters.event_type}`} />
              )}
              {appliedFilters.risk_level && (
                <Chip label={`risk: ${appliedFilters.risk_level}`} />
              )}
              {appliedFilters.actor_id && (
                <Chip label={`actor: ${appliedFilters.actor_id}`} />
              )}
              {appliedFilters.from_date && (
                <Chip label={`from: ${appliedFilters.from_date}`} />
              )}
              {appliedFilters.to_date && (
                <Chip label={`to: ${appliedFilters.to_date}`} />
              )}
            </div>
          )}
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <LoadingSkeleton />
          ) : !data || data.items.length === 0 ? (
            <EmptyState hasFilters={hasActiveFilters(appliedFilters)} />
          ) : (
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 z-10">
                <tr className="bg-paper-raised border-b border-paper-line">
                  <th className="px-3 py-2.5 w-5" />
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide whitespace-nowrap">
                    Timestamp
                  </th>
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide">
                    Event
                  </th>
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide">
                    Actor
                  </th>
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide">
                    Case ID
                  </th>
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide">
                    Client ID
                  </th>
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide">
                    Risk
                  </th>
                  <th className="px-3 py-2.5 text-left text-2xs font-semibold text-ink-muted uppercase tracking-wide">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((entry) => (
                  <PayloadRow key={entry.id} entry={entry} />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {data && data.total > PAGE_SIZE && (
          <div className="shrink-0 border-t border-paper-line bg-paper-raised px-6 py-3 flex items-center justify-between">
            <span className="text-xs text-ink-muted">
              Page {page} of {totalPages} ·{" "}
              {data.total.toLocaleString()} total
            </span>
            <div className="flex items-center gap-1">
              <PageBtn
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </PageBtn>
              {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
                const p = clampedPageList(page, totalPages)[i];
                if (p == null) return null;
                return (
                  <PageBtn
                    key={p}
                    onClick={() => setPage(p)}
                    active={p === page}
                  >
                    {p}
                  </PageBtn>
                );
              })}
              <PageBtn
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                <ChevronRightNav className="h-3.5 w-3.5" />
              </PageBtn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// === Small helpers ===

function Chip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-sm bg-accent-bg text-accent text-2xs font-medium border border-accent/20">
      {label}
    </span>
  );
}

function PageBtn({
  children,
  onClick,
  disabled,
  active,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "h-7 min-w-[28px] px-1.5 rounded text-xs font-medium flex items-center justify-center transition-colors",
        active
          ? "bg-accent text-paper-raised"
          : "text-ink-soft border border-paper-line hover:bg-paper-sunken hover:text-ink",
        disabled && "opacity-40 cursor-not-allowed hover:bg-transparent",
      )}
    >
      {children}
    </button>
  );
}

function clampedPageList(current: number, total: number): (number | null)[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, null, total];
  if (current >= total - 3) return [1, null, total - 4, total - 3, total - 2, total - 1, total];
  return [1, null, current - 1, current, current + 1, null, total];
}

function LoadingSkeleton() {
  return (
    <div className="p-6 space-y-2">
      {Array.from({ length: 12 }).map((_, i) => (
        <div
          key={i}
          className="h-9 rounded bg-paper-sunken animate-pulse"
          style={{ opacity: 1 - i * 0.06 }}
        />
      ))}
    </div>
  );
}

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
      <div className="h-12 w-12 rounded-full bg-paper-sunken flex items-center justify-center">
        <FileSearch className="h-6 w-6 text-ink-faint" strokeWidth={1.5} />
      </div>
      <div>
        <p className="text-sm font-medium text-ink-soft">
          {hasFilters ? "No entries match these filters" : "No audit entries yet"}
        </p>
        <p className="text-xs text-ink-faint mt-1">
          {hasFilters
            ? "Try adjusting your filters or clearing them to see all entries."
            : "Events will appear here as the system is used."}
        </p>
      </div>
    </div>
  );
}
