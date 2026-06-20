"use client";

import { cn } from "@/lib/utils";
import type { DriftCustomerDetail } from "@/types/api";
import { Globe, Building2, Link2, Newspaper, ShieldAlert, TrendingUp, Network, ExternalLink, BadgeAlert } from "lucide-react";

interface TwoLayerPanelProps {
  detail: DriftCustomerDetail;
}

const SIGNAL_ICON: Record<string, typeof Newspaper> = {
  news: Newspaper,
  sanctions: ShieldAlert,
  adverse_media: Newspaper,
  ownership_change: Network,
  funding_event: TrendingUp,
  business_model_change: Globe,
  name_change: BadgeAlert,
  domain_change: Link2,
};

const SIGNAL_LABEL: Record<string, string> = {
  news: "News",
  sanctions: "Sanctions",
  adverse_media: "Adverse media",
  ownership_change: "Ownership change",
  funding_event: "Funding event",
  business_model_change: "Business-model change",
  name_change: "Legal name change",
  domain_change: "Domain registrant change",
};

/**
 * Two-Layer Intelligence panel — the explicit AMINA Challenge 4 architecture:
 * Public Intelligence (external signals) + Internal Bank Data (drift),
 * fused via Confirmation Lift.
 *
 * The Confirmation Lift readout is the differentiator: it quantifies how
 * much an external signal and internal drift, co-occurring in time, raise
 * confidence beyond either alone.
 */
export function TwoLayerPanel({ detail }: TwoLayerPanelProps) {
  const {
    public_risk,
    internal_risk,
    confirmation_lift,
    public_signals,
    is_name_changed,
    is_business_model_change,
    business_model_distance,
  } = detail;
  const lifted = confirmation_lift > 1.5;
  // Only surface the business-model readout when a comparison actually ran
  // (distance > 0). A skipped comparison (no website texts / no embedder) leaves
  // the distance at its neutral 0.0, where "consistent" would be misleading.
  const showBusinessModel = business_model_distance > 0;

  const sevColor = (sev: number) => {
    if (sev >= 0.7) return "text-risk-critical";
    if (sev >= 0.4) return "text-risk-high";
    if (sev >= 0.2) return "text-risk-medium";
    return "text-ink-muted";
  };

  return (
    <div className="border border-paper-line rounded bg-paper-raised p-4">
      <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-3">
        Two-Layer Intelligence
      </h3>

      {/* The two layers side by side */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <LayerCard
          icon={Globe}
          label="Public Intelligence"
          sublabel="news · sanctions · media · ownership · funding"
          risk={public_risk}
        />
        <LayerCard
          icon={Building2}
          label="Internal Bank Data"
          sublabel="BOCPD drift · velocity · contagion"
          risk={internal_risk}
        />
      </div>

      {/* Confirmation lift connector */}
      <div
        className={cn(
          "flex items-center justify-center gap-2 rounded py-2 mb-3 border",
          lifted
            ? "bg-risk-high-bg border-risk-high/20"
            : "bg-paper-sunken border-paper-line",
        )}
      >
        <Link2
          className={cn("h-3.5 w-3.5", lifted ? "text-risk-high" : "text-ink-muted")}
          strokeWidth={2}
        />
        <span className={cn("text-xs", lifted ? "text-risk-high font-medium" : "text-ink-muted")}>
          Confirmation Lift{" "}
          <span className="font-mono font-semibold tabular">
            {confirmation_lift.toFixed(1)}x
          </span>
        </span>
        <span className="text-2xs text-ink-muted">
          {lifted
            ? "— external intelligence confirms internal drift"
            : "— layers independent"}
        </span>
      </div>

      {/* Identity reset (UC8): confirmed legal-entity name change → re-KYC. The
          name_change (ZEFIX) + domain_change (WHOIS) signals appear in the feed
          below; this callout makes the re-KYC trigger and the score-floor
          rationale explicit, since the transactions can look clean. */}
      {is_name_changed && (
        <div className="flex items-start gap-2 rounded py-2 px-2.5 mb-3 border bg-risk-medium-bg border-risk-medium/20">
          <BadgeAlert
            className="h-3.5 w-3.5 shrink-0 mt-0.5 text-risk-medium"
            strokeWidth={2}
          />
          <div className="min-w-0">
            <p className="text-xs font-medium text-risk-medium">
              Identity Reset — Re-KYC Triggered
            </p>
            <p className="text-2xs text-ink-muted mt-0.5 leading-snug">
              Confirmed legal-entity name change (ZEFIX) with a WHOIS registrant
              handover — the shelf-cycling pattern that resets the KYC review
              clock. The drift score is floored at 60 so the identity reset
              surfaces for review even when the transactions look clean.
            </p>
          </div>
        </div>
      )}

      {/* Business-model drift (UC 9): website/domain pivot since onboarding */}
      {showBusinessModel && (
        <div
          className={cn(
            "flex items-center gap-2 rounded py-2 px-2.5 mb-3 border",
            is_business_model_change
              ? "bg-risk-high-bg border-risk-high/20"
              : "bg-paper-sunken border-paper-line",
          )}
        >
          <Globe
            className={cn(
              "h-3.5 w-3.5 shrink-0",
              is_business_model_change ? "text-risk-high" : "text-ink-muted",
            )}
            strokeWidth={2}
          />
          <span
            className={cn(
              "text-xs",
              is_business_model_change ? "text-risk-high font-medium" : "text-ink-muted",
            )}
          >
            Business-Model Drift{" "}
            <span className="font-mono font-semibold tabular">
              {business_model_distance.toFixed(2)}
            </span>
          </span>
          <span className="text-2xs text-ink-muted">
            {is_business_model_change
              ? "— website pivoted materially since onboarding (Wayback↔Firecrawl)"
              : "— website consistent with onboarding"}
          </span>
        </div>
      )}

      {/* Public signals feed */}
      {public_signals.length > 0 ? (
        <div>
          <div className="text-2xs font-semibold uppercase tracking-wide text-ink-muted mb-2">
            External Signals
          </div>
          <ul className="space-y-1.5">
            {public_signals.map((s, i) => {
              const Icon = SIGNAL_ICON[s.signal_type] ?? Newspaper;
              // UC 10: a business-model pivot lifted to the critical band by two
              // independent sources (news event cluster + website cosine shift).
              // Two-source corroboration is far stronger than any single signal,
              // so give it a distinct critical treatment, not generic styling.
              const corroborated = s.corroborated;
              return (
                <li
                  key={i}
                  className={cn(
                    "flex items-start gap-2.5 py-1.5 border-b border-paper-line/50 last:border-0",
                    corroborated &&
                      "border-b-0 border border-risk-critical/30 bg-risk-critical-bg rounded px-2",
                  )}
                >
                  <span className="font-mono text-2xs text-ink-faint w-8 shrink-0 pt-0.5">
                    m{s.month}
                  </span>
                  <Icon
                    className={cn(
                      "h-3.5 w-3.5 shrink-0 mt-0.5",
                      corroborated ? "text-risk-critical" : sevColor(s.severity),
                    )}
                    strokeWidth={2}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs text-ink leading-snug">{s.headline}</p>
                      {corroborated && (
                        <span className="inline-flex shrink-0 items-center gap-1 rounded-sm bg-risk-critical/15 px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide text-risk-critical">
                          <Link2 className="h-2.5 w-2.5" strokeWidth={2.5} />
                          2-source corroborated
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-2xs text-ink-muted">
                      <span className="min-w-0 break-words">
                        {SIGNAL_LABEL[s.signal_type] ?? s.signal_type}
                      </span>
                      <span>·</span>
                      <span className="min-w-0 break-words">{s.source}</span>
                      {s.source_url && (
                        <>
                          <span>·</span>
                          <a
                            href={s.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex shrink-0 items-center gap-1 text-accent hover:text-ink transition-colors"
                          >
                            source
                            <ExternalLink className="h-2.5 w-2.5" strokeWidth={2} />
                          </a>
                        </>
                      )}
                      <span>·</span>
                      <span className={cn("shrink-0 font-mono tabular", sevColor(s.severity))}>
                        severity {s.severity.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="text-2xs text-ink-muted">No external signals for this customer.</p>
      )}
    </div>
  );
}

function LayerCard({
  icon: Icon,
  label,
  sublabel,
  risk,
}: {
  icon: typeof Globe;
  label: string;
  sublabel: string;
  risk: number;
}) {
  const pct = Math.round(risk * 100);
  const barColor =
    risk >= 0.6 ? "bg-risk-critical" : risk >= 0.3 ? "bg-risk-high" : risk >= 0.15 ? "bg-risk-medium" : "bg-risk-low";

  return (
    <div className="border border-paper-line rounded p-2.5 bg-paper">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="h-3.5 w-3.5 text-accent" strokeWidth={2} />
        <span className="text-xs font-semibold text-ink">{label}</span>
      </div>
      <div className="flex items-baseline gap-1.5 mb-1.5">
        <span className="font-mono text-lg font-semibold text-ink tabular">{pct}</span>
        <span className="text-2xs text-ink-muted">/ 100 risk</span>
      </div>
      <div className="h-1.5 bg-paper-sunken rounded-sm overflow-hidden mb-1.5">
        <div className={cn("h-full rounded-sm", barColor)} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-2xs text-ink-faint leading-tight">{sublabel}</p>
    </div>
  );
}
