"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Custom fallback. If not provided, uses default UI. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  /** Section name for the default error UI (e.g. "Risk Factors"). */
  section?: string;
  /** Called when the boundary catches an error (e.g. for logging). */
  onError?: (error: Error) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * React error boundary — catches render errors in children and shows a
 * graceful fallback instead of crashing the whole page.
 *
 * Used to isolate failures in independent sections of the Detail panel:
 * if SHAPViewer throws, Counterfactuals and Decision still work.
 *
 * Must be a class component — hooks can't catch render errors.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error) {
    this.props.onError?.(error);
    // In production you'd send to Sentry/Datadog here.
    // For demo we just log to console.
    console.error("[ErrorBoundary]", error);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return (
        <div className="border border-risk-medium/30 bg-risk-medium-bg rounded p-4">
          <div className="flex items-start gap-2.5">
            <AlertTriangle
              className="h-4 w-4 text-risk-medium shrink-0 mt-0.5"
              strokeWidth={2}
            />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-risk-medium mb-1">
                {this.props.section ?? "This section"} couldn&apos;t load
              </div>
              <p className="text-2xs text-ink-soft leading-relaxed mb-2">
                A render error was caught here. Other sections still work.
              </p>
              <button
                onClick={this.reset}
                className="inline-flex items-center gap-1 text-2xs text-risk-medium hover:underline font-medium"
              >
                <RefreshCw className="h-3 w-3" strokeWidth={2.5} />
                Try again
              </button>
              <details className="mt-2">
                <summary className="text-2xs text-ink-muted cursor-pointer hover:text-ink">
                  Error details
                </summary>
                <pre className="text-2xs text-ink-muted font-mono mt-1 whitespace-pre-wrap break-all">
                  {this.state.error.message}
                </pre>
              </details>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
