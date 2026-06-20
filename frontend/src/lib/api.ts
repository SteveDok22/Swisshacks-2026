/**
 * API client for the backend.
 *
 * Uses Next.js rewrites: /api/backend/* → http://localhost:8000/api/v1/*
 * (configured in next.config.mjs)
 *
 * This keeps the frontend code clean — no hardcoded localhost,
 * and avoids CORS issues in development.
 */

import type {
  AnonymizationPreview,
  AuditEntry,
  CaseDetail,
  CaseExplanation,
  CaseListItem,
  Client,
  CounterfactualResponse,
  DecisionAction,
  DecisionRead,
  JurisdictionAdjustedScore,
  PaginatedResponse,
  ScoringResponse,
} from "@/types/api";

const BASE = "/api/backend";

/**
 * Custom error class with HTTP status code preserved.
 * Lets UI distinguish "404 not found" from "500 server error" etc.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly endpoint: string,
  ) {
    super(`API ${status} on ${endpoint}: ${detail}`);
    this.name = "ApiError";
  }
}

/**
 * Wait helper for exponential backoff.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Generic fetch wrapper with timeout, retry, and typed errors.
 *
 * - Timeout: 15s default (Claude streaming can be slow)
 * - Retry: 1 retry on network failure or 5xx, with 500ms backoff
 * - Does NOT retry: 4xx errors (client errors, retrying won't help)
 */
async function apiFetch<T>(
  path: string,
  options?: RequestInit & { timeoutMs?: number; retries?: number },
): Promise<T> {
  const { timeoutMs = 15_000, retries = 1, ...fetchOptions } = options ?? {};
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(`${BASE}${path}`, {
        ...fetchOptions,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...fetchOptions.headers,
        },
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        const err = new ApiError(res.status, detail, path);
        // Don't retry client errors (4xx)
        if (res.status >= 400 && res.status < 500) {
          throw err;
        }
        lastError = err;
        // Retry 5xx after backoff
        if (attempt < retries) {
          await sleep(500 * (attempt + 1));
          continue;
        }
        throw err;
      }

      return res.json() as Promise<T>;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof ApiError) throw err; // already handled above
      if (err instanceof Error && err.name === "AbortError") {
        lastError = new Error(
          `Request timed out after ${timeoutMs}ms: ${path}`,
        );
      } else {
        lastError = err instanceof Error ? err : new Error(String(err));
      }
      // Network errors — retry
      if (attempt < retries) {
        await sleep(500 * (attempt + 1));
        continue;
      }
      throw lastError;
    }
  }

  throw lastError ?? new Error(`Unknown error fetching ${path}`);
}

// === Cases ===
export const casesApi = {
  list: (params?: {
    case_type?: string;
    status?: string;
    jurisdiction?: string;
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.case_type) qs.set("case_type", params.case_type);
    if (params?.status) qs.set("status", params.status);
    if (params?.jurisdiction) qs.set("jurisdiction", params.jurisdiction);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString();
    return apiFetch<PaginatedResponse<CaseListItem>>(
      `/cases${query ? `?${query}` : ""}`,
    );
  },

  get: (caseId: string) => apiFetch<CaseDetail>(`/cases/${caseId}`),

  history: (caseId: string) =>
    apiFetch<AuditEntry[]>(`/cases/${caseId}/history`),
};

// === Scoring ===
export const scoringApi = {
  score: (caseId: string) =>
    apiFetch<ScoringResponse>(`/scoring/${caseId}`, { method: "POST" }),
};

// === Counterfactuals ===
export const counterfactualsApi = {
  generate: (caseId: string, nScenarios = 3) =>
    apiFetch<CounterfactualResponse>(
      `/counterfactuals/${caseId}?n_scenarios=${nScenarios}`,
      { method: "POST" },
    ),
};

// === Explanations ===
export const explanationsApi = {
  generate: (caseId: string) =>
    apiFetch<CaseExplanation>(`/explanations/${caseId}`, { method: "POST" }),

  anonymization: (caseId: string) =>
    apiFetch<AnonymizationPreview>(`/explanations/${caseId}/anonymization`),

  /** Returns the SSE stream URL for the streaming explanation. */
  streamUrl: (caseId: string) => `${BASE}/explanations/${caseId}/stream`,
};

// === Jurisdictions ===
export const jurisdictionsApi = {
  compare: (caseId: string) =>
    apiFetch<Record<string, JurisdictionAdjustedScore>>(
      `/jurisdictions/compare/${caseId}`,
      { method: "POST" },
    ),
};

// === Clients ===
export const clientsApi = {
  list: () => apiFetch<Client[]>("/clients"),
  get: (clientId: string) => apiFetch<Client>(`/clients/${clientId}`),
};

// === Decisions ===
export const decisionsApi = {
  record: (payload: {
    case_id?: string;
    customer_id?: string;
    action: DecisionAction;
    officer_id: string;
    rationale?: string;
  }) =>
    apiFetch<DecisionRead>("/decisions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  forCase: (caseId: string) =>
    apiFetch<DecisionRead[]>(`/decisions/case/${caseId}`),

  forCustomer: (customerId: string) =>
    apiFetch<DecisionRead[]>(`/decisions/customer/${customerId}`),
};

// === Audit ===
export const auditApi = {
  search: (params?: {
    event_type?: string;
    risk_level?: string;
    actor_id?: string;
    customer_id?: string;
    from_date?: string;
    to_date?: string;
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.risk_level) qs.set("risk_level", params.risk_level);
    if (params?.actor_id) qs.set("actor_id", params.actor_id);
    if (params?.customer_id) qs.set("customer_id", params.customer_id);
    if (params?.from_date) qs.set("from_date", params.from_date);
    if (params?.to_date) qs.set("to_date", params.to_date);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString();
    return apiFetch<PaginatedResponse<AuditEntry>>(
      `/audit${query ? `?${query}` : ""}`,
    );
  },
};

// === Drift Engine (AMINA Challenge 4) ===
import type {
  DriftCustomerSummary,
  DriftCustomerDetail,
  CascadeCostReport,
  ContagionGraphData,
} from "@/types/api";

export const driftApi = {
  customers: () =>
    apiFetch<DriftCustomerSummary[]>("/drift/customers"),

  customer: (id: string) =>
    apiFetch<DriftCustomerDetail>(`/drift/customers/${id}`),

  scan: () =>
    apiFetch<CascadeCostReport>("/drift/scan", { method: "POST" }),

  contagion: () =>
    apiFetch<ContagionGraphData>("/drift/contagion"),

  replay: (id: string) =>
    apiFetch<import("@/types/api").ReplayResult>(`/drift/replay/${id}`),

  inject: (scenario: string, name: string) =>
    apiFetch<DriftCustomerDetail>("/drift/inject", {
      method: "POST",
      body: JSON.stringify({ scenario, name }),
    }),

  rfi: (id: string) =>
    apiFetch<{
      customer_id: string;
      questions: string[];
      rationale: string;
      estimated_info_gain_bits: number;
    }>(`/drift/rfi/${id}`, { method: "POST" }),
};
