"use client";

import { useQuery } from "@tanstack/react-query";
import { explanationsApi } from "@/lib/api";
import { Lock, ArrowRight, Shield } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface PrivacyPanelProps {
  caseId: string;
}

/**
 * Privacy-by-design transparency panel.
 *
 * Shows exactly what data leaves the bank vs what stays local.
 * Critical for FINMA-regulated banks (AMINA specifically) —
 * compliance officers can audit AI usage before approving.
 *
 * This is one of our key differentiators — most teams will send
 * raw client data to Claude.
 */
export function PrivacyPanel({ caseId }: PrivacyPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["anonymization", caseId],
    queryFn: () => explanationsApi.anonymization(caseId),
    staleTime: Infinity,
  });

  if (isLoading || !data) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Shield className="h-3.5 w-3.5 text-ink-muted" strokeWidth={2} />
        <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          Data Handling
        </h3>
        <span className="text-2xs text-ink-faint">· FINMA compliant</span>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left border border-paper-line rounded p-3.5 bg-paper-raised hover:bg-paper-sunken transition-colors"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-ink">
            {data.fields_redacted.length} fields redacted ·{" "}
            {data.fields_bucketed.length} bucketed
          </span>
          <span className="text-2xs text-accent">
            {expanded ? "Hide details" : "Show details →"}
          </span>
        </div>
        <p className="text-2xs text-ink-muted leading-relaxed">
          Client identifiers and exact amounts are anonymized before any AI
          call. The model reasons about patterns, not personal data.
        </p>
      </button>

      {expanded && (
        <div className="grid grid-cols-2 gap-3 animate-fade-in">
          {/* What stays local */}
          <div className="border border-paper-line rounded p-3 bg-paper-raised">
            <div className="flex items-center gap-1.5 mb-2.5">
              <Lock className="h-3 w-3 text-ink-soft" strokeWidth={2.5} />
              <span className="text-2xs font-semibold uppercase tracking-wide text-ink">
                Stays Local
              </span>
            </div>
            <ul className="space-y-1">
              {data.fields_redacted.map((field) => (
                <li
                  key={field}
                  className="text-2xs font-mono text-ink-soft capitalize"
                >
                  {field.replace(/_/g, " ")}
                </li>
              ))}
            </ul>
          </div>

          {/* What goes to AI */}
          <div className="border border-paper-line rounded p-3 bg-accent-bg">
            <div className="flex items-center gap-1.5 mb-2.5">
              <ArrowRight className="h-3 w-3 text-accent" strokeWidth={2.5} />
              <span className="text-2xs font-semibold uppercase tracking-wide text-accent">
                Goes to AI
              </span>
            </div>
            <ul className="space-y-1">
              {Object.entries(data.fields_sent_to_ai)
                .slice(0, 8)
                .map(([key, value]) => (
                  <li key={key} className="text-2xs">
                    <span className="font-mono text-ink-muted capitalize">
                      {key.replace(/_/g, " ")}:
                    </span>{" "}
                    <span className="font-mono text-ink">{value}</span>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
