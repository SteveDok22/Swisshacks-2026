"use client";

import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DriftCustomerDetail } from "@/types/api";

interface WebsiteDiffPanelProps {
  detail: DriftCustomerDetail;
}

function distanceBadge(distance: number): { label: string; className: string } {
  if (distance >= 0.35) {
    return {
      label: `High (${distance.toFixed(2)}) — pivot detected`,
      className: "bg-risk-high-bg text-risk-high border border-risk-high/20",
    };
  }
  if (distance >= 0.2) {
    return {
      label: `Moderate (${distance.toFixed(2)})`,
      className: "bg-risk-medium-bg text-risk-medium border border-risk-medium/20",
    };
  }
  return {
    label: `Low (${distance.toFixed(2)})`,
    className: "bg-risk-low-bg text-risk-low border border-risk-low/20",
  };
}

/**
 * Wayback↔Firecrawl website-drift panel (UC 9).
 *
 * Compact by design: a one-line AI summary of what changed between the
 * onboarding and current website, plus links to both versions (archived
 * snapshot + live site). The raw crawled text is intentionally NOT shown — it
 * is long and noisy; the LLM summary is the readable evidence.
 *
 * Only rendered when the business-model distance comparison actually ran.
 */
export function WebsiteDiffPanel({ detail }: WebsiteDiffPanelProps) {
  const {
    is_business_model_change,
    business_model_distance,
    onboarding_website_url,
    current_website_url,
    business_model_summary,
  } = detail;

  // Only render when a comparison ran — distance > 0 means the embedder ran.
  if (!is_business_model_change && (business_model_distance ?? 0) === 0) {
    return null;
  }

  const badge = distanceBadge(business_model_distance ?? 0);

  return (
    <div className="border border-paper-line rounded bg-paper-raised">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-paper-line">
        <h3 className="text-sm font-semibold text-ink">Website Business-Model Drift</h3>
        <span className={cn("text-2xs font-mono px-2 py-0.5 rounded font-medium", badge.className)}>
          {badge.label}
        </span>
      </div>

      <div className="p-4 space-y-3">
        {/* What changed — one short AI summary of the diff */}
        {business_model_summary && (
          <div>
            <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-1">
              What changed
            </div>
            <p className="text-sm text-ink leading-snug">{business_model_summary}</p>
          </div>
        )}

        {/* Compare the two versions */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-2xs text-ink-muted">Compare:</span>
          {onboarding_website_url && (
            <a
              href={onboarding_website_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-2xs font-medium text-accent hover:text-ink bg-paper-sunken px-2 py-1 rounded border border-paper-line transition-colors"
            >
              At onboarding (archived)
              <ExternalLink className="h-2.5 w-2.5" strokeWidth={2} />
            </a>
          )}
          {current_website_url && (
            <a
              href={current_website_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-2xs font-medium text-accent hover:text-ink bg-paper-sunken px-2 py-1 rounded border border-paper-line transition-colors"
            >
              Now (live site)
              <ExternalLink className="h-2.5 w-2.5" strokeWidth={2} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
