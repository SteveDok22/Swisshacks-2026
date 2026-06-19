"use client";

import { useQuery } from "@tanstack/react-query";
import { jurisdictionsApi } from "@/lib/api";
import { cn, ACTION_LABELS } from "@/lib/utils";
import { Scale, Loader2 } from "lucide-react";
import type { Jurisdiction } from "@/types/api";

interface JurisdictionSelectorProps {
  caseId: string;
  current: Jurisdiction;
  onSelect: (j: Jurisdiction) => void;
}

const JURISDICTIONS: { code: Jurisdiction; short: string; regulator: string }[] = [
  { code: "CH", short: "Switzerland", regulator: "FINMA" },
  { code: "EU", short: "EU", regulator: "MiCA" },
  { code: "HK", short: "Hong Kong", regulator: "SFC" },
  { code: "AE", short: "UAE", regulator: "FSRA" },
];

/**
 * Live jurisdiction comparison toggle.
 *
 * Demo killer for AMINA cross-jurisdictional challenge:
 * "Same case under FINMA → step-up. Under FSRA → escalate."
 *
 * Backend rescores the case under each jurisdiction's rule pack
 * (different thresholds, modifiers). Frontend shows the diff.
 */
export function JurisdictionSelector({
  caseId,
  current,
  onSelect,
}: JurisdictionSelectorProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["jurisdictions-compare", caseId],
    queryFn: () => jurisdictionsApi.compare(caseId),
    staleTime: 5 * 60_000,
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Scale className="h-3.5 w-3.5 text-ink-muted" strokeWidth={2} />
        <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Jurisdiction
        </h3>
        {isLoading && (
          <Loader2 className="h-3 w-3 animate-spin text-ink-faint" />
        )}
      </div>

      <div className="grid grid-cols-4 gap-2">
        {JURISDICTIONS.map((j) => {
          const isActive = current === j.code;
          const score = data?.[j.code];
          return (
            <button
              key={j.code}
              onClick={() => onSelect(j.code)}
              className={cn(
                "border rounded p-2.5 text-left transition-all",
                isActive
                  ? "border-accent bg-accent-bg ring-1 ring-accent/20"
                  : "border-paper-line bg-paper-raised hover:border-ink-faint",
              )}
            >
              <div className="flex items-baseline justify-between mb-0.5">
                <span
                  className={cn(
                    "text-2xs font-semibold",
                    isActive ? "text-accent" : "text-ink",
                  )}
                >
                  {j.code}
                </span>
                {score && (
                  <span
                    className={cn(
                      "font-mono tabular text-xs font-semibold",
                      isActive ? "text-accent" : "text-ink-soft",
                    )}
                  >
                    {score.adjusted_score.toFixed(0)}
                  </span>
                )}
              </div>
              <div className="text-2xs text-ink-muted leading-tight">
                {j.regulator}
              </div>
              {score && (
                <div
                  className={cn(
                    "text-2xs mt-1 truncate",
                    isActive ? "text-accent" : "text-ink-soft",
                  )}
                >
                  {ACTION_LABELS[score.recommended_action] ??
                    score.recommended_action}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Active jurisdiction's applicable rules */}
      {data?.[current]?.applicable_rules &&
        data[current].applicable_rules.length > 0 && (
          <div className="border border-paper-line rounded p-3 bg-paper-sunken">
            <div className="text-2xs font-semibold text-ink-muted mb-1.5 uppercase tracking-wide">
              Applicable under {data[current].jurisdiction_name}
            </div>
            <ul className="space-y-0.5">
              {data[current].applicable_rules.map((rule, i) => (
                <li key={i} className="text-2xs text-ink-soft leading-relaxed">
                  • {rule}
                </li>
              ))}
            </ul>
          </div>
        )}
    </div>
  );
}
