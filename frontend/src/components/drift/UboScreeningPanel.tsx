"use client";

import { cn } from "@/lib/utils";
import type { UboScreening } from "@/types/api";
import { ArrowRight, ExternalLink, ShieldAlert, ShieldCheck, Users } from "lucide-react";

interface UboScreeningPanelProps {
  hits: UboScreening[];
}

/**
 * UBO Screening panel (Case 5) — the new-shareholder / ownership-chain check.
 *
 * The aggregator resolves the customer's GLEIF ownership chain to names and
 * screens each through OpenSanctions. Hits above the match-score floor surface
 * here with the screened name, the matched watchlist entity, and the score.
 *
 * A definitive hit (score >= 0.85) is treated as critical; lower scores are
 * "probable" and call for manual confirmation. The clean ownership chain (no
 * hits) is shown explicitly so the absence of a signal is itself informative.
 */
export function UboScreeningPanel({ hits }: UboScreeningPanelProps) {
  const hasDefinitive = hits.some((h) => h.definitive);

  const scoreColor = (score: number) => {
    if (score >= 0.85) return "text-risk-critical";
    if (score >= 0.6) return "text-risk-high";
    if (score >= 0.4) return "text-risk-medium";
    return "text-ink-muted";
  };

  return (
    <div
      className={cn(
        "border rounded p-4",
        hasDefinitive
          ? "border-risk-critical/30 bg-risk-critical-bg"
          : "border-paper-line bg-paper-raised",
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <Users
          className={cn(
            "h-3.5 w-3.5",
            hasDefinitive ? "text-risk-critical" : "text-ink-muted",
          )}
          strokeWidth={2}
        />
        <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
          UBO Screening — ownership-chain sanctions
        </h3>
        {hasDefinitive && (
          <span className="text-2xs px-2 py-0.5 rounded font-medium bg-risk-critical text-white">
            HIT
          </span>
        )}
      </div>

      {hits.length > 0 ? (
        <ul className="space-y-1.5">
          {hits.map((h, i) => (
            <li
              key={`${h.screened_ubo}-${h.matched_entity}-${i}`}
              className="flex items-start gap-2.5 py-1.5 border-b border-paper-line/50 last:border-0"
            >
              <span className="font-mono text-2xs text-ink-faint w-8 shrink-0 pt-0.5">
                m{h.month}
              </span>
              <ShieldAlert
                className={cn("h-3.5 w-3.5 shrink-0 mt-0.5", scoreColor(h.score))}
                strokeWidth={2}
              />
              <div className="flex-1 min-w-0">
                <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-ink leading-snug">
                  <span className="font-medium break-words">{h.screened_ubo}</span>
                  <ArrowRight className="h-3 w-3 text-ink-faint shrink-0" strokeWidth={2} />
                  <span className="break-words">{h.matched_entity}</span>
                </p>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-2xs text-ink-muted">
                  <span
                    className={cn(
                      "shrink-0 px-1.5 py-0.5 rounded font-medium",
                      h.definitive
                        ? "bg-risk-critical text-white"
                        : "bg-risk-medium-bg text-risk-medium",
                    )}
                  >
                    {h.definitive ? "definitive" : "probable"}
                  </span>
                  <span className={cn("shrink-0 font-mono tabular", scoreColor(h.score))}>
                    match {h.score.toFixed(2)}
                  </span>
                  <span>·</span>
                  <span className="shrink-0 font-mono tabular">
                    severity {h.severity.toFixed(2)}
                  </span>
                  {h.source_url && (
                    <>
                      <span>·</span>
                      <a
                        href={h.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex shrink-0 items-center gap-1 text-accent hover:text-ink transition-colors"
                      >
                        watchlist
                        <ExternalLink className="h-2.5 w-2.5" strokeWidth={2} />
                      </a>
                    </>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex items-center gap-2 text-2xs text-ink-muted">
          <ShieldCheck className="h-3.5 w-3.5 text-risk-low shrink-0" strokeWidth={2} />
          No UBO sanctions hits — resolved ownership chain is clear.
        </div>
      )}

      {hasDefinitive && (
        <p className="text-2xs text-risk-critical mt-2 leading-relaxed font-medium">
          A beneficial owner in the ownership chain matched a sanctions watchlist
          with high confidence — surfaced for human AML review.
        </p>
      )}
    </div>
  );
}
