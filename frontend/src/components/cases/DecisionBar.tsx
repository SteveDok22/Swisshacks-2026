"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { decisionsApi } from "@/lib/api";
import { cn, ACTION_LABELS } from "@/lib/utils";
import { Check, ChevronUp, AlertOctagon, ShieldAlert, X } from "lucide-react";
import type { DecisionAction } from "@/types/api";

type DecisionBarProps = {
  aiRecommendedAction: DecisionAction | null;
} & (
  | { caseId: string; driftId?: never }
  | { driftId: string; caseId?: never }
);

const ACTIONS: {
  action: DecisionAction;
  icon: typeof Check;
  variant: "low" | "medium" | "high" | "critical";
}[] = [
  { action: "allow", icon: Check, variant: "low" },
  { action: "step_up_verification", icon: ChevronUp, variant: "medium" },
  { action: "escalate", icon: AlertOctagon, variant: "high" },
  { action: "block", icon: ShieldAlert, variant: "critical" },
];

const VARIANT_STYLES: Record<string, { base: string; hover: string; ring: string }> = {
  low: {
    base: "border-risk-low/30 text-risk-low",
    hover: "hover:bg-risk-low-bg hover:border-risk-low",
    ring: "ring-risk-low/20",
  },
  medium: {
    base: "border-risk-medium/30 text-risk-medium",
    hover: "hover:bg-risk-medium-bg hover:border-risk-medium",
    ring: "ring-risk-medium/20",
  },
  high: {
    base: "border-risk-high/30 text-risk-high",
    hover: "hover:bg-risk-high-bg hover:border-risk-high",
    ring: "ring-risk-high/20",
  },
  critical: {
    base: "border-risk-critical/30 text-risk-critical",
    hover: "hover:bg-risk-critical-bg hover:border-risk-critical",
    ring: "ring-risk-critical/20",
  },
};

/**
 * Decision bar — sticky bottom action surface.
 *
 * Supports two workflows:
 * - Case review: pass `caseId`; decision is recorded against a case.
 * - Drift engine: pass `driftId`; decision is recorded against a drift customer.
 *
 * In both cases the AI's recommended action is highlighted with a ring so
 * officers can see when they're overriding it.  Override requires a rationale.
 *
 * Decision is logged immutably via /decisions with a full audit trail.
 */
export function DecisionBar(props: DecisionBarProps) {
  const { aiRecommendedAction } = props;
  const [pendingAction, setPendingAction] = useState<DecisionAction | null>(
    null,
  );
  const [rationale, setRationale] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const queryClient = useQueryClient();

  const isDrift = "driftId" in props;
  const subjectId = isDrift ? props.driftId : props.caseId;

  const mutation = useMutation({
    mutationFn: (payload: {
      action: DecisionAction;
      rationale?: string;
    }) =>
      decisionsApi.record(
        isDrift
          ? {
              drift_id: props.driftId,
              action: payload.action,
              officer_id: "anna.mueller@amina.ch",
              rationale: payload.rationale,
            }
          : {
              case_id: props.caseId,
              action: payload.action,
              officer_id: "anna.mueller@amina.ch",
              rationale: payload.rationale,
            },
      ),
    onSuccess: () => {
      setSubmitted(true);
      setPendingAction(null);
      setRationale("");
      if (isDrift) {
        queryClient.invalidateQueries({ queryKey: ["drift-customers"] });
        queryClient.invalidateQueries({ queryKey: ["drift-customer", subjectId] });
        queryClient.invalidateQueries({ queryKey: ["audit"] });
      } else {
        queryClient.invalidateQueries({ queryKey: ["cases"] });
        queryClient.invalidateQueries({ queryKey: ["case", subjectId] });
        queryClient.invalidateQueries({ queryKey: ["case-history", subjectId] });
        queryClient.invalidateQueries({ queryKey: ["audit"] });
      }
    },
  });

  const handleClick = (action: DecisionAction) => {
    const isOverride =
      aiRecommendedAction !== null && action !== aiRecommendedAction;
    if (isOverride) {
      setPendingAction(action);
    } else {
      mutation.mutate({ action });
    }
  };

  const handleSubmitOverride = () => {
    if (!pendingAction || rationale.trim().length < 10) return;
    mutation.mutate({ action: pendingAction, rationale: rationale.trim() });
  };

  if (submitted) {
    return (
      <div className="border-t border-paper-line bg-risk-low-bg px-6 py-4 flex items-center gap-3 animate-fade-in">
        <div className="h-6 w-6 rounded-full bg-risk-low flex items-center justify-center">
          <Check className="h-3.5 w-3.5 text-paper-raised" strokeWidth={3} />
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-risk-low">
            Decision recorded
          </div>
          <div className="text-2xs text-ink-soft">
            Immutably logged to audit trail
          </div>
        </div>
        <button
          onClick={() => setSubmitted(false)}
          className="text-2xs text-ink-muted hover:text-ink"
        >
          Reset
        </button>
      </div>
    );
  }

  if (pendingAction) {
    const variant = ACTIONS.find((a) => a.action === pendingAction)!.variant;
    return (
      <div className="border-t border-paper-line bg-paper-raised px-6 py-4 animate-slide-up">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-xs font-medium text-ink">
              Override AI recommendation
            </div>
            <div className="text-2xs text-ink-muted">
              AI suggested{" "}
              <span className="font-semibold">
                {ACTION_LABELS[aiRecommendedAction!]}
              </span>
              , you&apos;re recording{" "}
              <span
                className={cn("font-semibold", VARIANT_STYLES[variant].base)}
              >
                {ACTION_LABELS[pendingAction]}
              </span>
            </div>
          </div>
          <button
            onClick={() => {
              setPendingAction(null);
              setRationale("");
            }}
            className="text-ink-muted hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Required: rationale for overriding AI recommendation (min 10 chars)"
          rows={2}
          className="w-full border border-paper-line rounded px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent resize-none"
        />
        <div className="flex items-center justify-between mt-2">
          <span className="text-2xs text-ink-muted">
            {rationale.length} / 10 minimum
          </span>
          <button
            onClick={handleSubmitOverride}
            disabled={
              rationale.trim().length < 10 || mutation.isPending
            }
            className={cn(
              "px-3 py-1.5 rounded text-xs font-medium",
              rationale.trim().length >= 10
                ? "bg-accent text-paper-raised hover:bg-accent-soft"
                : "bg-paper-sunken text-ink-faint cursor-not-allowed",
            )}
          >
            {mutation.isPending ? "Recording…" : "Record decision"}
          </button>
        </div>
        {mutation.isError && (
          <div className="mt-2 text-2xs text-risk-critical">
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Could not record decision"}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="border-t border-paper-line bg-paper-raised px-6 py-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Decision
        </div>
        {aiRecommendedAction && (
          <div className="text-2xs text-ink-muted">
            AI suggests:{" "}
            <span className="font-medium text-ink">
              {ACTION_LABELS[aiRecommendedAction]}
            </span>
          </div>
        )}
      </div>
      <div className="grid grid-cols-4 gap-2">
        {ACTIONS.map(({ action, icon: Icon, variant }) => {
          const isAiChoice = action === aiRecommendedAction;
          const v = VARIANT_STYLES[variant];
          return (
            <button
              key={action}
              onClick={() => handleClick(action)}
              disabled={mutation.isPending}
              className={cn(
                "flex items-center justify-center gap-1.5 border rounded py-2 text-xs font-medium transition-all",
                v.base,
                v.hover,
                isAiChoice && `ring-1 ${v.ring}`,
              )}
            >
              <Icon className="h-3.5 w-3.5" strokeWidth={2} />
              {ACTION_LABELS[action]}
            </button>
          );
        })}
      </div>
      {mutation.isError && (
        <div className="mt-2 text-2xs text-risk-critical">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Could not record decision"}
        </div>
      )}
    </div>
  );
}
