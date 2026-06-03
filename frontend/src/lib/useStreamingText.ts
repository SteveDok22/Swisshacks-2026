"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseStreamingTextResult {
  text: string;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  /** Number of automatic retry attempts so far (0-2). */
  retryCount: number;
  start: () => void;
  reset: () => void;
  /** Manually retry after error. Resets retry counter. */
  retry: () => void;
}

const MAX_AUTO_RETRIES = 2;
const RETRY_DELAY_MS = 800;

/**
 * React hook for consuming a Server-Sent Events stream.
 *
 * Used for the "live AI thinking" effect — words appear progressively
 * as Claude generates the explanation.
 *
 * Error handling strategy:
 * - Network errors (connection lost mid-stream): auto-retry up to 2 times
 *   with 800ms delay between attempts
 * - Server-sent error events (model registry miss, anonymizer failure):
 *   surface immediately, no auto-retry (likely deterministic), expose
 *   manual retry via returned `retry()` function
 *
 * The endpoint contract (backend/app/api/v1/explanations.py):
 *   event: message  data: <chunk>
 *   event: done     data: (empty)
 *   event: error    data: <error message>
 *
 * @param url SSE endpoint URL. Pass `null` to disable.
 */
export function useStreamingText(url: string | null): UseStreamingTextResult {
  const [text, setText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0); // sync ref for closures

  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    closeStream();
    setText("");
    setIsStreaming(false);
    setIsDone(false);
    setError(null);
    setRetryCount(0);
    retryCountRef.current = 0;
  }, [closeStream]);

  const openStream = useCallback(() => {
    if (!url) return;
    setIsStreaming(true);
    setError(null);

    const source = new EventSource(url);
    eventSourceRef.current = source;

    // Track if we received any data — if yes, we don't retry on disconnect
    // (partial stream is better than starting over).
    let hasReceivedData = false;

    source.addEventListener("message", (e: MessageEvent) => {
      hasReceivedData = true;
      setText((prev) => prev + e.data);
    });

    source.addEventListener("done", () => {
      setIsStreaming(false);
      setIsDone(true);
      closeStream();
    });

    // Server-sent error event — deterministic failure, surface immediately
    source.addEventListener("error", (e: Event) => {
      const data = (e as MessageEvent).data;
      // Native onerror events have no .data; SSE error events do
      if (data) {
        setError(String(data));
        setIsStreaming(false);
        closeStream();
        return;
      }

      // Native connection error (network glitch, server restart)
      if (
        !hasReceivedData &&
        retryCountRef.current < MAX_AUTO_RETRIES
      ) {
        retryCountRef.current += 1;
        setRetryCount(retryCountRef.current);
        closeStream();
        retryTimerRef.current = setTimeout(openStream, RETRY_DELAY_MS);
      } else {
        // Either we've already received data (don't restart) or exceeded retries
        setError(
          hasReceivedData
            ? "Stream interrupted"
            : "Could not connect to stream",
        );
        setIsStreaming(false);
        closeStream();
      }
    });
  }, [url, closeStream]);

  const start = useCallback(() => {
    reset();
    openStream();
  }, [reset, openStream]);

  const retry = useCallback(() => {
    retryCountRef.current = 0;
    setRetryCount(0);
    setError(null);
    setText("");
    setIsDone(false);
    openStream();
  }, [openStream]);

  // Auto-cleanup on unmount
  useEffect(() => {
    return () => {
      closeStream();
    };
  }, [closeStream]);

  return {
    text,
    isStreaming,
    isDone,
    error,
    retryCount,
    start,
    reset,
    retry,
  };
}
