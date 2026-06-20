"use client";

import { ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";
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
  const [resizeKey, setResizeKey] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let frame = 0;

    const handleResize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        setResizeKey((key) => key + 1);
      });
    };

    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  // Lock background scroll and allow Escape to close while zoomed.
  useEffect(() => {
    if (!zoomed) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setZoomed(false);
    };
    window.addEventListener("keydown", handleKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKey);
    };
  }, [zoomed]);

  const overlay = (
    <div
      className="fixed inset-0 z-[100] overflow-y-auto bg-ink/45"
      role="dialog"
      aria-modal="true"
      onClick={() => setZoomed(false)}
    >
      {/* Inner wrapper guarantees vertical+horizontal centering while still
          allowing scroll when the content is taller than the viewport. */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          key={resizeKey}
          className={cn(
            "relative w-[min(980px,calc(100vw-2rem))] max-h-[90vh] overflow-auto shadow-raised [&_svg:not(.lucide)]:mx-auto [&_svg:not(.lucide)]:h-auto [&_svg:not(.lucide)]:max-h-[58vh] [&_svg:not(.lucide)]:w-full",
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
    </div>
  );

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

      {zoomed && mounted ? createPortal(overlay, document.body) : null}
    </>
  );
}
