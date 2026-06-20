"use client";

import { useId } from "react";
import { cn } from "@/lib/utils";
import { Info } from "lucide-react";

interface InfoHintProps {
  text: string;
  className?: string;
}

export function InfoHint({ text, className }: InfoHintProps) {
  const tooltipId = useId();

  return (
    <span className={cn("relative inline-flex group", className)}>
      <button
        type="button"
        aria-label={text}
        aria-describedby={tooltipId}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-paper-line bg-paper text-ink-muted transition-colors hover:border-accent/40 hover:text-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
      >
        <Info className="h-3 w-3" strokeWidth={2} />
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none fixed left-1/2 top-16 z-[80] hidden w-[min(40rem,calc(100vw-2rem))] -translate-x-1/2 rounded border border-paper-line bg-ink px-3 py-2 text-left text-2xs font-normal leading-relaxed text-paper shadow-raised group-hover:block group-focus-within:block"
      >
        {text}
      </span>
    </span>
  );
}
