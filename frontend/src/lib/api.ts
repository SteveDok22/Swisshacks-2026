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

/** Generic fetch wrapper with error handling. */
async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }

  return res.json() as Promise<T>;
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
    case_id: string;
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
};

// === Audit ===
export const auditApi = {
  search: (params?: {
    event_type?: string;
    risk_level?: string;
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.risk_level) qs.set("risk_level", params.risk_level);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString();
    return apiFetch<PaginatedResponse<AuditEntry>>(
      `/audit${query ? `?${query}` : ""}`,
    );
  },
};
