"use client";

import { cn } from "@/lib/utils";
import type { DriftCustomerDetail } from "@/types/api";

interface WebsiteDiffPanelProps {
  detail: DriftCustomerDetail;
}

const MAX_CHARS = 500;

function truncate(text: string): string {
  if (text.length <= MAX_CHARS) return text;
  return text.slice(0, MAX_CHARS) + "...";
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
 * Wayback↔Firecrawl website diff panel (UC 9 / Phase G3).
 *
 * Shows the onboarding vs current website text side-by-side so a compliance
 * officer can read the evidence behind the cosine-distance business-model
 * change signal.
 *
 * Only rendered when the business-model distance comparison actually ran.
 */
export function WebsiteDiffPanel({ detail }: WebsiteDiffPanelProps) {
  const { is_business_model_change, business_model_distance, onboarding_website_text, current_website_text } = detail;

  // Only render when a comparison ran — distance > 0 means embedder ran.
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

      {/* Two-column diff */}
      <div className="grid grid-cols-2 divide-x divide-paper-line">
        {/* Left: onboarding snapshot */}
        <div className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xs font-semibold text-ink-soft">At Onboarding (Wayback)</span>
            <span className="text-2xs text-ink-faint font-mono bg-paper-sunken px-1 py-0.5 rounded border border-paper-line">
              archive.org
            </span>
          </div>
          {onboarding_website_text ? (
            <p className="whitespace-pre-wrap text-xs font-mono text-ink-soft leading-relaxed">
              {truncate(onboarding_website_text)}
            </p>
          ) : (
            <p className="text-xs text-ink-muted italic">No snapshot available</p>
          )}
        </div>

        {/* Right: current snapshot */}
        <div className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xs font-semibold text-ink-soft">Now (Firecrawl)</span>
            <span className="text-2xs text-ink-faint font-mono bg-paper-sunken px-1 py-0.5 rounded border border-paper-line">
              firecrawl
            </span>
          </div>
          {current_website_text ? (
            <p className="whitespace-pre-wrap text-xs font-mono text-ink-soft leading-relaxed">
              {truncate(current_website_text)}
            </p>
          ) : (
            <p className="text-xs text-ink-muted italic">No snapshot available</p>
          )}
        </div>
      </div>
    </div>
  );
}
