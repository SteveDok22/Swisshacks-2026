import { cn, riskColors } from "@/lib/utils";
import type { RiskLevel } from "@/types/api";

interface RiskScoreProps {
  score: number | null;
  level: RiskLevel | null;
  size?: "sm" | "md" | "lg";
}

/**
 * Numeric risk score, 0-100, with monospace tabular figures.
 * The mono font + tabular nums keeps scores aligned in lists —
 * a small detail that signals "financial precision".
 */
export function RiskScore({ score, level, size = "md" }: RiskScoreProps) {
  const colors = riskColors(level);

  if (score === null) {
    return <span className="font-mono text-ink-faint text-sm">—</span>;
  }

  return (
    <span
      className={cn(
        "font-mono font-semibold tabular leading-none",
        colors.text,
        size === "sm" && "text-sm",
        size === "md" && "text-base",
        size === "lg" && "text-3xl",
      )}
    >
      {score.toFixed(size === "lg" ? 1 : 0)}
      {size === "lg" && (
        <span className="text-ink-faint text-sm font-normal ml-1">/100</span>
      )}
    </span>
  );
}
