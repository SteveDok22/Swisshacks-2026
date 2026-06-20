"use client";

import { cn } from "@/lib/utils";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";

interface InfoHintProps {
  text: string;
  className?: string;
}

export function InfoHint({ text, className }: InfoHintProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={200}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          <button
            type="button"
            aria-label={text}
            className={cn(
              "inline-flex h-5 w-5 items-center justify-center rounded-full border border-paper-line bg-paper text-ink-muted transition-colors hover:border-accent/40 hover:text-accent focus:outline-none focus:ring-2 focus:ring-accent/20",
              className,
            )}
          >
            <Info className="h-3 w-3" strokeWidth={2} />
          </button>
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side="top"
            align="center"
            collisionPadding={12}
            className="z-[110] w-[min(20rem,calc(100vw-2rem))] rounded border border-paper-line bg-ink px-3 py-2 text-left text-2xs font-normal leading-relaxed text-paper shadow-raised data-[state=delayed-open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=delayed-open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=delayed-open]:zoom-in-95"
          >
            {text}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
