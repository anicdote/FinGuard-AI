/**
 * FinGuard AI — API Client
 * Handles JWT auth, auto-refresh, and normalises backend responses
 * (snake_case → camelCase, ISO strings → Date objects).
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── Token storage ─────────────────────────────────────────────────────────────
export const tokenStore = {
  get access(): string | null  { return localStorage.getItem("fg_access"); },
  get refresh(): string | null { return localStorage.getItem("fg_refresh"); },
  set(access: string, refresh: string) {
    localStorage.setItem("fg_access",  access);
    localStorage.setItem("fg_refresh", refresh);
  },
  clear() {
    localStorage.removeItem("fg_access");
    localStorage.removeItem("fg_refresh");
  },
};

// ── snake_case → camelCase deep converter ─────────────────────────────────────
function toCamel(s: string): string {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function normalizeDates(obj: any): any {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj === "string") {
    // Convert ISO datetime strings to Date objects
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(obj)) return new Date(obj);
    return obj;
  }
  if (obj instanceof Date) return obj;
  if (Array.isArray(obj)) return obj.map(normalizeDates);
  if (typeof obj === "object") {
    const out: any = {};
    for (const [k, v] of Object.entries(obj)) {
      out[toCamel(k)] = normalizeDates(v);
    }
    return out;
  }
  return obj;
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────
async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> ?? {}),
  };

  if (tokenStore.access) {
    headers["Authorization"] = `Bearer ${tokenStore.access}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && retry && tokenStore.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) return apiFetch<T>(path, options, false);
    tokenStore.clear();
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API error");
  }

  const raw = await res.json();
  // Normalize all responses: snake_case keys → camelCase, ISO strings → Dates
  return normalizeDates(raw) as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(
      `${BASE_URL}/api/v1/auth/refresh?refresh_token=${tokenStore.refresh}`,
      { method: "POST" },
    );
    if (!res.ok) return false;
    const data = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// ── Auth API ──────────────────────────────────────────────────────────────────
export const authApi = {
  async login(email: string, password: string) {
    const form = new URLSearchParams({ username: email, password });
    const res  = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? "Login failed");
    }
    const data = await res.json();
    tokenStore.set(data.access_token, data.refresh_token);
    return data;
  },

  logout() {
    tokenStore.clear();
    window.location.href = "/login";
  },

  me: () => apiFetch<{ _id: string; email: string; name: string; role: "admin" | "manager" | "officer" | "analyst" }>("/api/v1/auth/me"),
};

// ── Transaction API ───────────────────────────────────────────────────────────
export const transactionApi = {
  list:      (limit = 50, skip = 0) => apiFetch<any[]>(`/api/v1/transactions/?limit=${limit}&skip=${skip}`),
  get:       (id: string)           => apiFetch<any>(`/api/v1/transactions/${id}`),
  byAccount: (accountId: string)    => apiFetch<any[]>(`/api/v1/transactions/account/${accountId}`),
  stats:     ()                     => apiFetch<any>("/api/v1/transactions/stats"),
  create:    (txn: object)          => apiFetch<any>("/api/v1/transactions/", { method: "POST", body: JSON.stringify(txn) }),
};

// ── Case API ──────────────────────────────────────────────────────────────────
export const caseApi = {
  list: (params?: { status?: string; priority?: string; limit?: number }) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v !== undefined)) as any
    ).toString();
    return apiFetch<any[]>(`/api/v1/cases/?${q}`);
  },
  get:          (id: string)                             => apiFetch<any>(`/api/v1/cases/${id}`),
  summary:      ()                                       => apiFetch<any>("/api/v1/cases/summary"),
  updateStatus: (id: string, status: string, notes = "") =>
    apiFetch<any>(`/api/v1/cases/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, analyst_notes: notes }),
    }),
  acceptRecommendation: (id: string) =>
    apiFetch<any>(`/api/v1/cases/${id}/review/accept`, { method: "POST" }),
  overrideRecommendation: (id: string, decision: string, reason: string) =>
    apiFetch<any>(`/api/v1/cases/${id}/review/override`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    }),
  requestMoreEvidence: (id: string, request: string) =>
    apiFetch<any>(`/api/v1/cases/${id}/review/more-evidence`, {
      method: "POST",
      body: JSON.stringify({ request }),
    }),
  assign: (id: string, officerId: string) =>
    apiFetch<any>(`/api/v1/cases/${id}/assign`, {
      method: "POST",
      body: JSON.stringify({ officer_id: officerId }),
    }),
  markFalsePositive: (id: string, reason: string, notes = "") =>
    apiFetch<any>(`/api/v1/cases/${id}/false-positive`, {
      method: "POST",
      body: JSON.stringify({ reason, notes }),
    }),
  falsePositiveStats: () =>
    apiFetch<any>("/api/v1/cases/false-positive-stats"),
  audit: (id: string, limit = 100) =>
    apiFetch<any[]>(`/api/v1/cases/${id}/audit?limit=${limit}`),
};

// ── Users API (Phase 8 — case assignment) ──────────────────────────────────────
export const userApi = {
  listOfficers: () => apiFetch<any[]>("/api/v1/users/officers"),
};

// ── Analytics API ─────────────────────────────────────────────────────────────
export const analyticsApi = {
  dashboard: () => apiFetch<any>("/api/v1/analytics/dashboard"),
  trend:     (days = 30) => apiFetch<any[]>(`/api/v1/analytics/trend?days=${days}`),
};

// ── Predictions API ───────────────────────────────────────────────────────────
export const predictionsApi = {
  score:     (txn: object)   => apiFetch<any>("/api/v1/predictions/score", { method: "POST", body: JSON.stringify(txn) }),
  modelInfo: ()               => apiFetch<any>("/api/v1/predictions/model-info"),
};
