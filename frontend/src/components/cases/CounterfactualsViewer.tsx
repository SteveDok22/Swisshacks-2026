"use client";

import { useQuery } from "@tanstack/react-query";
import { counterfactualsApi } from "@/lib/api";
import { GitBranch, Loader2 } from "lucide-react";

interface CounterfactualsViewerProps {
  caseId: string;
}

/**
 * "What would change the decision?" scenarios from DiCE.
 *
 * One of our key differentiators — most teams will show SHAP only.
 * Counterfactuals turn the AI from a black box into a conversation partner:
 * "show me what would make this acceptable".
 *
 * Only meaningful for high/critical cases — backend returns empty list
 * for low-risk cases.
 */
export function CounterfactualsViewer({ caseId }: CounterfactualsViewerProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["counterfactuals", caseId],
    queryFn: () => counterfactualsApi.generate(caseId, 3),
    staleTime: 5 * 60_000, // 5 min — expensive to compute
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-ink-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Computing alternative scenarios…
      </div>
    );
  }

  if (!data) {
    return null;
  }

  // Hide section entirely for low-risk cases (no useful counterfactuals)
  if (data.counterfactuals.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <GitBranch className="h-3.5 w-3.5 text-ink-muted" strokeWidth={2} />
        <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Alternative Scenarios
        </h3>
        <span className="text-2xs text-ink-faint">
          · what would make this approvable
        </span>
      </div>

      <div className="space-y-2">
        {data.counterfactuals.map((cf, i) => (
          <div
            key={cf.scenario_id}
            className="border border-paper-line rounded p-3.5 bg-paper-raised animate-slide-up opacity-0"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xs font-mono font-semibold text-ink-muted">
                Scenario {cf.scenario_id}
              </span>
              <span className="inline-flex items-center gap-1 text-2xs text-risk-low">
                <span className="h-1.5 w-1.5 rounded-full bg-risk-low" />
                would become low risk
              </span>
            </div>
            <p className="text-xs text-ink leading-relaxed">
              {cf.summary}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
