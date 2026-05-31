"use client";

import { useEffect } from "react";
import { useStreamingText } from "@/lib/useStreamingText";
import { explanationsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Sparkles } from "lucide-react";

interface StreamingExplanationProps {
  caseId: string;
}

/**
 * Live AI explanation streamed via SSE.
 *
 * The signature UX moment: words appear progressively as Claude generates
 * them, with a blinking cursor. Feels like watching the AI "think".
 *
 * Auto-starts on mount and when caseId changes.
 */
export function StreamingExplanation({ caseId }: StreamingExplanationProps) {
  const { text, isStreaming, isDone, error, start, reset } = useStreamingText(
    explanationsApi.streamUrl(caseId),
  );

  // Auto-start stream when case changes
  useEffect(() => {
    reset();
    // Small delay so reset state propagates
    const t = setTimeout(start, 100);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles
            className={cn(
              "h-3.5 w-3.5",
              isStreaming ? "text-accent animate-pulse" : "text-ink-muted",
            )}
            strokeWidth={2}
          />
          <h3 className="text-2xs font-semibold uppercase tracking-wide text-ink-muted">
            AI Assessment
          </h3>
          {isStreaming && (
            <span className="text-2xs text-accent">analyzing…</span>
          )}
        </div>
      </div>

      <div className="bg-paper-raised border border-paper-line rounded p-4">
        {error ? (
          <div className="text-xs text-risk-critical">
            Stream error: {error}
          </div>
        ) : (
          <p className="text-sm text-ink leading-relaxed">
            {text}
            {isStreaming && (
              <span className="inline-block w-1.5 h-3.5 bg-accent ml-0.5 align-middle animate-pulse" />
            )}
            {!text && !isStreaming && !isDone && (
              <span className="text-ink-faint">Starting analysis…</span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
