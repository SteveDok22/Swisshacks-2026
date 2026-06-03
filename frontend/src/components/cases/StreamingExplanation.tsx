"use client";

import { useEffect } from "react";
import { useStreamingText } from "@/lib/useStreamingText";
import { explanationsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Sparkles, RefreshCw, AlertCircle } from "lucide-react";

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
 * On error: shows what was received so far (if any) + retry button.
 */
export function StreamingExplanation({ caseId }: StreamingExplanationProps) {
  const { text, isStreaming, isDone, error, retryCount, start, reset, retry } =
    useStreamingText(explanationsApi.streamUrl(caseId));

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
          {isStreaming && retryCount === 0 && (
            <span className="text-2xs text-accent">analyzing…</span>
          )}
          {isStreaming && retryCount > 0 && (
            <span className="text-2xs text-risk-medium">
              reconnecting (attempt {retryCount + 1})…
            </span>
          )}
          {isDone && !error && (
            <span className="text-2xs text-ink-muted">· complete</span>
          )}
        </div>
        {(isDone || error) && (
          <button
            onClick={retry}
            className="inline-flex items-center gap-1 text-2xs text-ink-muted hover:text-ink"
            title="Regenerate the assessment"
          >
            <RefreshCw className="h-3 w-3" strokeWidth={2} />
            Regenerate
          </button>
        )}
      </div>

      <div className="bg-paper-raised border border-paper-line rounded p-4">
        {error && !text ? (
          /* Pure error state — no text received */
          <div className="flex items-start gap-2">
            <AlertCircle
              className="h-4 w-4 text-risk-medium shrink-0 mt-0.5"
              strokeWidth={2}
            />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-ink mb-1">
                AI stream unavailable
              </div>
              <p className="text-2xs text-ink-muted leading-relaxed mb-2">
                The SHAP factors and counterfactuals below are still based on the
                ML model and don&apos;t require this stream.
              </p>
              <button
                onClick={retry}
                className="inline-flex items-center gap-1 text-2xs text-accent hover:underline font-medium"
              >
                <RefreshCw className="h-3 w-3" strokeWidth={2.5} />
                Try again
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-ink leading-relaxed">
              {text}
              {isStreaming && (
                <span className="inline-block w-1.5 h-3.5 bg-accent ml-0.5 align-middle animate-pulse" />
              )}
              {!text && !isStreaming && !isDone && (
                <span className="text-ink-faint">Starting analysis…</span>
              )}
            </p>
            {error && text && (
              /* Partial error — show what we got, with a note */
              <div className="mt-2 pt-2 border-t border-paper-line flex items-center gap-1.5 text-2xs text-risk-medium">
                <AlertCircle className="h-3 w-3" strokeWidth={2.5} />
                Stream interrupted —{" "}
                <button onClick={retry} className="underline hover:no-underline">
                  retry
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
