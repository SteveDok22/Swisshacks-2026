"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { configApi } from "@/lib/api";
import type { ConfigMode } from "@/types/api";

const WELCOME_KEY = "sentinel.welcome-seen";

const FALLBACK: ConfigMode = {
  mode: "synthetic",
  external_apis_enabled: false,
  llm_mode: "mock",
  active_adapters: [],
};

/**
 * Mode-aware badge in the top-right corner of the workspace.
 *
 * Shows SYNTHETIC (amber) or LIVE (green pulsing) depending on the backend
 * config mode. Clicking opens a small dropdown with mode details and the
 * welcome-modal reset escape hatch.
 */
export function DemoModeBadge() {
  const [showHelp, setShowHelp] = useState(false);

  const { data, isError, isLoading } = useQuery({
    queryKey: ["config-mode"],
    queryFn: configApi.getMode,
    refetchInterval: 30000,
  });

  const config: ConfigMode = isError || isLoading || !data ? FALLBACK : data;
  const isLive = config.mode === "live";

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
        title="Mode controls"
      >
        {isLive ? (
          <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
        ) : (
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        )}
        {isLive ? "LIVE" : "SYNTHETIC"}
      </button>

      {showHelp && (
        <div className="absolute top-full right-0 mt-1.5 w-72 border border-paper-line bg-paper-raised rounded shadow-raised animate-scale-in">
          <div className="px-3 py-2.5 border-b border-paper-line">
            <div className="text-xs font-semibold text-ink">
              {isLive ? "Live API mode" : "Synthetic demo mode"}
            </div>
            <p className="text-2xs text-ink-muted mt-0.5 leading-relaxed">
              {isLive
                ? config.active_adapters.length > 0
                  ? config.active_adapters.join(", ")
                  : "No adapters active"
                : "All signals are generated from deterministic scenarios. No external API calls."}
            </p>
          </div>

          {/* LLM status row */}
          <div className="px-3 py-2 border-b border-paper-line flex items-center gap-2">
            {config.llm_mode === "live" ? (
              <span className="h-1.5 w-1.5 rounded-full bg-green-400 shrink-0" />
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
            )}
            <span className={cn(
              "text-2xs",
              config.llm_mode === "live" ? "text-green-600" : "text-amber-600",
            )}>
              {config.llm_mode === "live" ? "Claude API: connected" : "Claude API: mock mode"}
            </span>
          </div>

          <div className="border-t border-paper-line" />

          <button
            onClick={resetWelcome}
            className="w-full px-3 py-2 text-left text-xs text-ink-soft hover:bg-paper-sunken transition-colors"
          >
            Reset welcome modal
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
