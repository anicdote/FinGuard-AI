/**
 * FinGuard AI — API Client
 *
 * Handles:
 * - Password authentication
 * - Biometric login challenge creation/polling
 * - JWT storage
 * - Automatic token refresh
 * - Backend snake_case → frontend camelCase conversion
 * - Existing transaction/case/user/analytics/prediction APIs
 */

const BASE_URL = "http://localhost:8000";

// ─────────────────────────────────────────────────────────────────────────────
// Token storage
// ─────────────────────────────────────────────────────────────────────────────

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem("fg_access");
  },

  get refresh(): string | null {
    return localStorage.getItem("fg_refresh");
  },

  set(access: string, refresh: string) {
    localStorage.setItem("fg_access", access);
    localStorage.setItem("fg_refresh", refresh);
  },

  clear() {
    localStorage.removeItem("fg_access");
    localStorage.removeItem("fg_refresh");
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Biometric challenge token storage
// ─────────────────────────────────────────────────────────────────────────────
//
// The login POST returns a short-lived challenge_token.
// Keep it in memory only. It is NOT a JWT.
//
// If your backend version does not require this header, sending it is harmless.
// If the backend does require it, this prevents the previous 422 error.
// ─────────────────────────────────────────────────────────────────────────────

let biometricChallengeToken: string | null = null;

function setBiometricChallengeToken(token?: string | null) {
  biometricChallengeToken = token ?? null;
}

function clearBiometricChallengeToken() {
  biometricChallengeToken = null;
}

// ─────────────────────────────────────────────────────────────────────────────
// snake_case → camelCase + ISO dates
// ─────────────────────────────────────────────────────────────────────────────

function toCamel(value: string): string {
  return value.replace(
    /_([a-z])/g,
    (_, character) => character.toUpperCase(),
  );
}

function normalizeDates(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (typeof obj === "string") {
    if (
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(obj)
    ) {
      return new Date(obj);
    }

    return obj;
  }

  if (obj instanceof Date) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(normalizeDates);
  }

  if (typeof obj === "object") {
    const output: any = {};

    for (const [key, value] of Object.entries(obj)) {
      output[toCamel(key)] = normalizeDates(value);
    }

    return output;
  }

  return obj;
}

// ─────────────────────────────────────────────────────────────────────────────
// Core API fetch wrapper
// ─────────────────────────────────────────────────────────────────────────────

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
    headers["Authorization"] =
      `Bearer ${tokenStore.access}`;
  }

  const response = await fetch(
    `${BASE_URL}${path}`,
    {
      ...options,
      headers,
    },
  );

  // ─────────────────────────────────────────────────────────────────────────
  // Automatic JWT refresh
  // ─────────────────────────────────────────────────────────────────────────

  if (
    response.status === 401 &&
    retry &&
    tokenStore.refresh
  ) {
    const refreshed = await tryRefresh();

    if (refreshed) {
      return apiFetch<T>(
        path,
        options,
        false,
      );
    }

    tokenStore.clear();

    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }

    throw new Error("Session expired");
  }

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({
        detail: response.statusText,
      }));

    throw new Error(
      error.detail ?? "API error",
    );
  }

  const raw = await response.json();

  return normalizeDates(raw) as T;
}

// ─────────────────────────────────────────────────────────────────────────────
// JWT refresh
// ─────────────────────────────────────────────────────────────────────────────

async function tryRefresh(): Promise<boolean> {
  if (!tokenStore.refresh) {
    return false;
  }

  try {
    const response = await fetch(
      `${BASE_URL}/api/v1/auth/refresh?refresh_token=${encodeURIComponent(
        tokenStore.refresh,
      )}`,
      {
        method: "POST",
      },
    );

    if (!response.ok) {
      return false;
    }

    const data = await response.json();

    tokenStore.set(
      data.access_token,
      data.refresh_token,
    );

    return true;
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Authentication API
// ─────────────────────────────────────────────────────────────────────────────

export const authApi = {
  /**
   * Start password + biometric authentication.
   *
   * Password is verified by the backend.
   * The backend then starts the local fingerprint challenge.
   *
   * IMPORTANT:
   * This function does NOT store JWTs because the backend does not
   * issue JWTs until the fingerprint succeeds.
   */
  async beginLogin(
    email: string,
    password: string,
  ) {
    clearBiometricChallengeToken();

    const form = new URLSearchParams();

    form.set("username", email);
    form.set("password", password);

    const response = await fetch(
      `${BASE_URL}/api/v1/auth/login`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/x-www-form-urlencoded",
        },
        body: form,
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({}));

      throw new Error(
        error.detail ?? "Login failed",
      );
    }

    const raw = await response.json();

    const data = normalizeDates(raw);

    // Backend may return challenge_token.
    if (data.challengeToken) {
      setBiometricChallengeToken(
        data.challengeToken,
      );
    }

    return data;
  },

  /**
   * Backwards-compatible login alias.
   */
  async login(
    email: string,
    password: string,
  ) {
    return this.beginLogin(
      email,
      password,
    );
  },

  /**
   * Poll the server-side biometric challenge.
   *
   * The browser does NOT talk to Arduino.
   * It only asks the backend for the current challenge state.
   */
  async checkLoginChallenge(
    challengeId: string,
  ) {
    const headers: Record<string, string> = {};

    if (biometricChallengeToken) {
      headers[
        "X-Biometric-Challenge-Token"
      ] = biometricChallengeToken;
    }

    const data = await apiFetch<any>(
      `/api/v1/auth/biometric-challenges/${encodeURIComponent(
        challengeId,
      )}`,
      {
        headers,
      },
    );

    // JWTs are stored ONLY after fingerprint verification.
    if (
      data.accessToken &&
      data.refreshToken
    ) {
      tokenStore.set(
        data.accessToken,
        data.refreshToken,
      );

      clearBiometricChallengeToken();
    }

    return data;
  },

  logout() {
    tokenStore.clear();
    clearBiometricChallengeToken();

    window.location.href = "/login";
  },

  me: () =>
    apiFetch<{
      _id: string;
      email: string;
      name: string;
      role:
        | "admin"
        | "manager"
        | "officer"
        | "analyst";
    }>(
      "/api/v1/auth/me",
    ),
};

// ─────────────────────────────────────────────────────────────────────────────
// Transaction API
// ─────────────────────────────────────────────────────────────────────────────

export const transactionApi = {
  list: (
    limit = 50,
    skip = 0,
  ) =>
    apiFetch<any[]>(
      `/api/v1/transactions/?limit=${limit}&skip=${skip}`,
    ),

  get: (id: string) =>
    apiFetch<any>(
      `/api/v1/transactions/${id}`,
    ),

  byAccount: (
    accountId: string,
  ) =>
    apiFetch<any[]>(
      `/api/v1/transactions/account/${accountId}`,
    ),

  stats: () =>
    apiFetch<any>(
      "/api/v1/transactions/stats",
    ),

  create: (txn: object) =>
    apiFetch<any>(
      "/api/v1/transactions/",
      {
        method: "POST",
        body: JSON.stringify(txn),
      },
    ),
};

// ─────────────────────────────────────────────────────────────────────────────
// Case API
// ─────────────────────────────────────────────────────────────────────────────

export const caseApi = {
  list: (
    params?: {
      status?: string;
      priority?: string;
      limit?: number;
    },
  ) => {
    const query = new URLSearchParams(
      Object.fromEntries(
        Object.entries(
          params ?? {},
        ).filter(
          ([, value]) =>
            value !== undefined,
        ),
      ) as any,
    ).toString();

    return apiFetch<any[]>(
      `/api/v1/cases/?${query}`,
    );
  },

  get: (id: string) =>
    apiFetch<any>(
      `/api/v1/cases/${id}`,
    ),

  summary: () =>
    apiFetch<any>(
      "/api/v1/cases/summary",
    ),

  updateStatus: (
    id: string,
    status: string,
    notes = "",
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${id}/status`,
      {
        method: "PATCH",
        body: JSON.stringify({
          status,
          analyst_notes: notes,
        }),
      },
    ),

  acceptRecommendation: (
    id: string,
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${id}/review/accept`,
      {
        method: "POST",
      },
    ),

  overrideRecommendation: (
    id: string,
    decision: string,
    reason: string,
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${id}/review/override`,
      {
        method: "POST",
        body: JSON.stringify({
          decision,
          reason,
        }),
      },
    ),

  requestMoreEvidence: (
    id: string,
    request: string,
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${id}/review/more-evidence`,
      {
        method: "POST",
        body: JSON.stringify({
          request,
        }),
      },
    ),

  assign: (
    id: string,
    officerId: string,
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${id}/assign`,
      {
        method: "POST",
        body: JSON.stringify({
          officer_id: officerId,
        }),
      },
    ),

  markFalsePositive: (
    id: string,
    reason: string,
    notes = "",
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${id}/false-positive`,
      {
        method: "POST",
        body: JSON.stringify({
          reason,
          notes,
        }),
      },
    ),

  falsePositiveStats: () =>
    apiFetch<any>(
      "/api/v1/cases/false-positive-stats",
    ),

  audit: (
    id: string,
    limit = 100,
  ) =>
    apiFetch<any[]>(
      `/api/v1/cases/${id}/audit?limit=${limit}`,
    ),

  // ─────────────────────────────────────────────────────────────────────────
  // STR biometric authorization
  // ─────────────────────────────────────────────────────────────────────────

  beginStrBiometricChallenge: (
    caseId: string,
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${caseId}/str/biometric-challenge`,
      {
        method: "POST",
      },
    ),

  checkStrBiometricChallenge: (
    caseId: string,
    challengeId: string,
  ) =>
    apiFetch<any>(
      `/api/v1/cases/${caseId}/str/biometric-challenge/${encodeURIComponent(
        challengeId,
      )}`,
    ),
};

// ─────────────────────────────────────────────────────────────────────────────
// Users API
// ─────────────────────────────────────────────────────────────────────────────

export const userApi = {
  listOfficers: () =>
    apiFetch<any[]>(
      "/api/v1/users/officers",
    ),
};

// ─────────────────────────────────────────────────────────────────────────────
// Analytics API
// ─────────────────────────────────────────────────────────────────────────────

export const analyticsApi = {
  dashboard: () =>
    apiFetch<any>(
      "/api/v1/analytics/dashboard",
    ),

  trend: (days = 30) =>
    apiFetch<any[]>(
      `/api/v1/analytics/trend?days=${days}`,
    ),
};

// ─────────────────────────────────────────────────────────────────────────────
// Predictions API
// ─────────────────────────────────────────────────────────────────────────────

export const predictionsApi = {
  score: (txn: object) =>
    apiFetch<any>(
      "/api/v1/predictions/score",
      {
        method: "POST",
        body: JSON.stringify(txn),
      },
    ),

  modelInfo: () =>
    apiFetch<any>(
      "/api/v1/predictions/model-info",
    ),
};