"use client";

import { useEffect, useRef, useState } from "react";

interface UseStreamingTextResult {
  text: string;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  start: () => void;
  reset: () => void;
}

/**
 * React hook for consuming a Server-Sent Events stream.
 *
 * Used for the "live AI thinking" effect — words appear progressively
 * as Claude generates the explanation.
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
  const eventSourceRef = useRef<EventSource | null>(null);

  const reset = () => {
    setText("");
    setIsStreaming(false);
    setIsDone(false);
    setError(null);
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const start = () => {
    if (!url) return;
    reset();
    setIsStreaming(true);

    const source = new EventSource(url);
    eventSourceRef.current = source;

    source.addEventListener("message", (e: MessageEvent) => {
      setText((prev) => prev + e.data);
    });

    source.addEventListener("done", () => {
      setIsStreaming(false);
      setIsDone(true);
      source.close();
      eventSourceRef.current = null;
    });

    source.addEventListener("error", (e: MessageEvent) => {
      // sse-starlette sends "error" events with detail in e.data
      const msg = typeof e === "object" && "data" in e ? String(e.data) : "Stream error";
      setError(msg);
      setIsStreaming(false);
      source.close();
      eventSourceRef.current = null;
    });
  };

  // Auto-cleanup on unmount or URL change
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return { text, isStreaming, isDone, error, start, reset };
}
