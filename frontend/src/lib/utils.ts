import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { RiskLevel } from "@/types/api";

/** Merge Tailwind classes safely (handles conflicts). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format a CHF amount with Swiss conventions. */
export function formatCHF(amount: number): string {
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: "CHF",
    maximumFractionDigits: 0,
  }).format(amount);
}

/** Format a relative time (e.g. "12 min ago"). */
export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.round((now - then) / 1000);

  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} h ago`;
  return `${Math.floor(diffSec / 86400)} d ago`;
}

/** Format an ISO timestamp as a readable date-time. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Map a risk level to Tailwind color classes. */
export function riskColors(level: RiskLevel | null): {
  text: string;
  bg: string;
  border: string;
  dot: string;
} {
  switch (level) {
    case "low":
      return {
        text: "text-risk-low",
        bg: "bg-risk-low-bg",
        border: "border-risk-low/20",
        dot: "bg-risk-low",
      };
    case "medium":
      return {
        text: "text-risk-medium",
        bg: "bg-risk-medium-bg",
        border: "border-risk-medium/20",
        dot: "bg-risk-medium",
      };
    case "high":
      return {
        text: "text-risk-high",
        bg: "bg-risk-high-bg",
        border: "border-risk-high/20",
        dot: "bg-risk-high",
      };
    case "critical":
      return {
        text: "text-risk-critical",
        bg: "bg-risk-critical-bg",
        border: "border-risk-critical/20",
        dot: "bg-risk-critical",
      };
    default:
      return {
        text: "text-ink-muted",
        bg: "bg-paper-sunken",
        border: "border-paper-line",
        dot: "bg-ink-faint",
      };
  }
}

/** Human-readable labels for case types. */
export const CASE_TYPE_LABELS: Record<string, string> = {
  social_engineering: "Social Engineering",
  portfolio_risk: "Portfolio Risk",
  investment_recommendation: "Investment Recommendation",
  client_onboarding: "Client Onboarding",
  xrpl_transaction: "XRPL Transaction",
};

/** Human-readable labels for jurisdictions. */
export const JURISDICTION_LABELS: Record<string, string> = {
  CH: "Switzerland · FINMA",
  EU: "European Union · MiCA",
  HK: "Hong Kong · SFC",
  AE: "UAE · FSRA",
};

/** Human-readable labels for decision actions. */
export const ACTION_LABELS: Record<string, string> = {
  allow: "Allow",
  step_up_verification: "Step-up Verification",
  escalate: "Escalate",
  block: "Block",
};
