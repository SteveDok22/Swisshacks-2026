import { cn, riskColors } from "@/lib/utils";
import type { RiskLevel } from "@/types/api";

interface RiskBadgeProps {
  level: RiskLevel | null;
  size?: "sm" | "md";
  showDot?: boolean;
}

/**
 * Risk level badge — the semantic color anchor of the whole UI.
 * The dot + label pattern reads instantly in a dense queue.
 */
export function RiskBadge({ level, size = "md", showDot = true }: RiskBadgeProps) {
  const colors = riskColors(level);
  const label = level ? level.charAt(0).toUpperCase() + level.slice(1) : "Unscored";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm font-medium border",
        colors.text,
        colors.bg,
        colors.border,
        size === "sm" ? "px-1.5 py-0.5 text-2xs" : "px-2 py-1 text-xs",
      )}
    >
      {showDot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", colors.dot)} />
      )}
      {label}
    </span>
  );
}
