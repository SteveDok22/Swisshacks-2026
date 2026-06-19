"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

const WELCOME_KEY = "sentinel.welcome-seen";

/**
 * Discrete "DEMO" badge in the top-right corner of the workspace.
 *
 * Two purposes:
 * 1. Honest disclosure to anyone using the dashboard that this is a
 *    hackathon demo, not production.
 * 2. Hidden escape hatch: clicking the badge resets the welcome modal,
 *    which is useful for showing it to a colleague mid-demo without
 *    having to open DevTools and clear localStorage manually.
 *
 * Designed to be NOT distracting during the actual pitch — small,
 * monochrome, in a corner.
 */
export function DemoModeBadge() {
  const [showHelp, setShowHelp] = useState(false);

  const resetWelcome = () => {
    try {
      localStorage.removeItem(WELCOME_KEY);
      window.location.reload();
    } catch {
      // Ignore — privacy mode or similar
    }
  };

  return (
    <div className="fixed top-3 right-3 z-40">
      <button
        onClick={() => setShowHelp(!showHelp)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2 py-1 rounded",
          "border border-paper-line bg-paper-raised/95 backdrop-blur-sm",
          "text-2xs font-mono font-medium text-ink-muted",
          "hover:border-ink-faint hover:text-ink transition-colors",
          "shadow-sm",
        )}
        title="Demo mode controls"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-risk-medium" />
        DEMO
      </button>

      {showHelp && (
        <div className="absolute top-full right-0 mt-1.5 w-64 border border-paper-line bg-paper-raised rounded shadow-raised animate-scale-in">
          <div className="px-3 py-2.5 border-b border-paper-line">
            <div className="text-xs font-semibold text-ink">
              Hackathon demo build
            </div>
            <p className="text-2xs text-ink-muted mt-0.5 leading-relaxed">
              Mock data, mock-mode AI responses unless ANTHROPIC_API_KEY is set.
            </p>
          </div>
          <button
            onClick={resetWelcome}
            className="w-full px-3 py-2 text-left text-xs text-ink-soft hover:bg-paper-sunken transition-colors"
          >
            Show welcome modal again
          </button>
          <button
            onClick={() => setShowHelp(false)}
            className="w-full px-3 py-2 text-left text-2xs text-ink-muted hover:bg-paper-sunken transition-colors border-t border-paper-line"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}
