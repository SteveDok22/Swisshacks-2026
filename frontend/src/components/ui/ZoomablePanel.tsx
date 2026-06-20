"use client";

import { ReactNode, useState } from "react";
import { cn } from "@/lib/utils";
import { Maximize2, X } from "lucide-react";

interface ZoomablePanelProps {
  children: ReactNode;
  className?: string;
  zoomLabel?: string;
}

export function ZoomablePanel({
  children,
  className,
  zoomLabel = "Zoom visualization",
}: ZoomablePanelProps) {
  const [zoomed, setZoomed] = useState(false);

  return (
    <>
      <div className={cn("relative", className)}>
        <button
          type="button"
          onClick={() => setZoomed(true)}
          aria-label={zoomLabel}
          className="absolute right-2 top-2 z-10 inline-flex h-7 w-7 items-center justify-center rounded border border-paper-line bg-paper-raised/95 text-ink-muted shadow-card transition-colors hover:border-accent/40 hover:text-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
        >
          <Maximize2 className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
        {children}
      </div>

      {zoomed && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-ink/45 px-4 pb-4 overflow-y-auto"
          role="dialog"
          aria-modal="true"
          onClick={() => setZoomed(false)}
        >
          <div
            className={cn(
              "relative max-h-[92vh] w-[min(1120px,calc(100vw-2rem))] overflow-auto shadow-raised",
              className,
            )}
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setZoomed(false)}
              aria-label="Close zoomed visualization"
              className="absolute right-2 top-2 z-20 inline-flex h-8 w-8 items-center justify-center rounded border border-paper-line bg-paper-raised/95 text-ink-muted shadow-card transition-colors hover:border-risk-critical/40 hover:text-risk-critical focus:outline-none focus:ring-2 focus:ring-risk-critical/20"
            >
              <X className="h-4 w-4" strokeWidth={2} />
            </button>
            {children}
          </div>
        </div>
      )}
    </>
  );
}
