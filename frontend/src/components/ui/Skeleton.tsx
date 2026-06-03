import { cn } from "@/lib/utils";

/**
 * Animated skeleton placeholder.
 *
 * Used while content is loading — gives a sense of "almost ready"
 * instead of "frozen" that a "Loading…" text creates.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "bg-paper-sunken rounded animate-pulse",
        className,
      )}
    />
  );
}

/** SHAP viewer skeleton — 5 horizontal bars. */
export function SHAPSkeleton() {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-[1fr_auto] gap-3 items-center"
        >
          <div>
            <Skeleton className="h-3 w-3/4 mb-1.5" />
            <Skeleton className="h-1.5 w-full" />
          </div>
          <Skeleton className="h-3 w-14" />
        </div>
      ))}
    </div>
  );
}

/** Counterfactual cards skeleton — 3 cards. */
export function CounterfactualsSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="border border-paper-line rounded p-3.5 bg-paper-raised"
        >
          <Skeleton className="h-3 w-32 mb-2" />
          <Skeleton className="h-3 w-full mb-1" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}

/** Jurisdiction selector skeleton — 4 cards in a row. */
export function JurisdictionSkeleton() {
  return (
    <div className="grid grid-cols-4 gap-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-16" />
      ))}
    </div>
  );
}

/** Streaming text skeleton — paragraph placeholder. */
export function StreamingSkeleton() {
  return (
    <div className="bg-paper-raised border border-paper-line rounded p-4 space-y-2">
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-11/12" />
      <Skeleton className="h-3 w-4/5" />
    </div>
  );
}
