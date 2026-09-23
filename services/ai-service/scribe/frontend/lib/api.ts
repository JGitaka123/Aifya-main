import { mockData } from "./mockData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";

class ApiError extends Error {
  status: number;
  trace_id?: string;
  retryable: boolean;
  constructor(message: string, status: number, trace_id?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.trace_id = trace_id;
    // 5xx and network errors are retryable, 4xx are not
    this.retryable = status >= 500 || status === 0;
  }
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("aifya_access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/** Exponential backoff delay */
function backoffDelay(attempt: number, baseMs = 500, maxMs = 8000): number {
  const delay = Math.min(baseMs * Math.pow(2, attempt), maxMs);
  // Add jitter: +/- 25%
  return delay * (0.75 + Math.random() * 0.5);
}

/** In-flight request deduplication for GET requests */
const inflightRequests = new Map<string, Promise<any>>();

interface RequestOptions extends RequestInit {
  /** Number of retry attempts for transient failures (default: 2) */
  retries?: number;
  /** Skip deduplication for this request */
  skipDedup?: boolean;
  /** Abort signal timeout in milliseconds */
  timeoutMs?: number;
}

async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  if (USE_MOCK) {
    console.log(`[MOCK API] Request to ${path}`);
    await new Promise((r) => setTimeout(r, 300)); // Simulate network delay

    if (path.startsWith("/auth/login")) return mockData.auth.login as T;
    if (path.startsWith("/auth/profile")) return mockData.auth.profile as T;
    if (path.startsWith("/patients/")) {
      if (path.includes("/encounters")) return mockData.patients.encounters as T;
      return mockData.patients.lookup as T;
    }
    if (path.startsWith("/scribe/process")) return mockData.scribe.process as T;
    if (path.startsWith("/scribe/extract")) return mockData.scribe.extract as T;
    if (path.startsWith("/claims/stats")) return mockData.claims.stats as T;
    if (path.startsWith("/claims")) return mockData.claims.list as T;
    if (path.startsWith("/discharge/generate")) return mockData.discharge.generate as T;
    if (path.startsWith("/discharge/")) return mockData.discharge.get as T;
    if (path.startsWith("/admin/users")) return mockData.admin.users as T;
    if (path.startsWith("/admin/audit-log")) return mockData.admin.auditLog as T;
    if (path.startsWith("/admin/sync-status")) return mockData.admin.syncStatus as T;
    if (path.startsWith("/health")) return mockData.health as any as T;

    console.warn(`[MOCK API] No mock data for ${path}, returning empty object`);
    return {} as T;
  }

  const { retries = 2, skipDedup = false, timeoutMs = 30000, ...fetchOptions } = options;
  const url = `${API_BASE}${path}`;
  const method = (fetchOptions.method || "GET").toUpperCase();

  const headers: Record<string, string> = {
    ...getAuthHeaders(),
    ...(fetchOptions.headers as Record<string, string> || {}),
  };

  // Only set application/json if not FormData
  if (!(fetchOptions.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  // Deduplicate identical in-flight GET requests
  const dedupKey = `${method}:${url}`;
  if (method === "GET" && !skipDedup && inflightRequests.has(dedupKey)) {
    return inflightRequests.get(dedupKey) as Promise<T>;
  }

  const execute = async (attempt: number): Promise<T> => {
    // Create abort controller for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(url, {
        ...fetchOptions,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        let message = `Request failed: ${res.status}`;
        let trace_id: string | undefined;
        try {
          const body = await res.json();
          if (Array.isArray(body.detail)) {
            // Extract messages from FastAPI validation errors
            message = body.detail.map((d: any) => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join(", ");
          } else {
            message = body.detail || body.error || message;
          }
          trace_id = body.details?.trace_id;
        } catch { }

        const error = new ApiError(message, res.status, trace_id);

        // Auto-logout on 401
        if (res.status === 401 && typeof window !== "undefined") {
          localStorage.removeItem("aifya_access_token");
          localStorage.removeItem("aifya_user");
          document.cookie = "aifya_access_token=; path=/; max-age=0";
          // Redirect to login if not already there
          if (!window.location.pathname.startsWith("/login")) {
            window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
          }
        }

        // Retry on transient errors
        if (error.retryable && attempt < retries) {
          const delay = backoffDelay(attempt);
          await new Promise((r) => setTimeout(r, delay));
          return execute(attempt + 1);
        }

        throw error;
      }

      if (res.status === 204) return {} as T;
      return res.json();
    } catch (err) {
      clearTimeout(timeoutId);

      // Handle timeout / network errors
      if (err instanceof DOMException && err.name === "AbortError") {
        const timeoutError = new ApiError("Request timed out", 0);
        if (attempt < retries) {
          const delay = backoffDelay(attempt);
          await new Promise((r) => setTimeout(r, delay));
          return execute(attempt + 1);
        }
        throw timeoutError;
      }

      // Network failure retry
      if (err instanceof TypeError && err.message.includes("fetch") && attempt < retries) {
        const delay = backoffDelay(attempt);
        await new Promise((r) => setTimeout(r, delay));
        return execute(attempt + 1);
      }

      throw err;
    }
  };

  const promise = execute(0).finally(() => {
    inflightRequests.delete(dedupKey);
  });

  if (method === "GET" && !skipDedup) {
    inflightRequests.set(dedupKey, promise);
  }

  return promise;
}

// Auth
export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{
        access_token: string;
        refresh_token: string;
        expires_in: number;
        user: { id: string; email: string; full_name: string; role: string; is_active: boolean };
      }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }), retries: 0 }),

    register: (data: { email: string; password: string; full_name: string; role: string; license_no?: string }) =>
      request("/auth/register", { method: "POST", body: JSON.stringify(data), retries: 0 }),

    logout: () => request("/auth/logout", { method: "POST", retries: 0 }),

    changePassword: (current_password: string, new_password: string) =>
      request("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password, new_password }),
        retries: 0,
      }),

    profile: () => request<any>("/auth/profile"),

    updateProfile: (data: { full_name?: string; license_no?: string }) =>
      request("/auth/profile", { method: "PUT", body: JSON.stringify(data), retries: 0 }),
  },

  patients: {
    lookup: (identifier: string) => request<any>(`/patients/${encodeURIComponent(identifier)}`),
    encounters: (patientId: string, limit = 20) =>
      request<any[]>(`/patients/${encodeURIComponent(patientId)}/encounters?limit=${limit}`),
  },

  scribe: {
    extract: (transcript: string) =>
      request<any>("/scribe/extract", {
        method: "POST",
        body: JSON.stringify({ transcript }),
        timeoutMs: 60000, // LLM extraction can be slow
      }),
    process: (transcript: string) =>
      request<any>("/scribe/process", {
        method: "POST",
        body: JSON.stringify({ transcript }),
        timeoutMs: 60000,
      }),
    transcribe: (audioBlob: Blob) => {
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      return request<{ transcript: string }>("/scribe/transcribe", {
        method: "POST",
        body: formData,
        headers: {}, // Let browser set multipart/form-data boundary
        timeoutMs: 60000,
      }).then((res) => res.transcript);
    },
    addendum: (encounter_id: string, addendum_text: string) =>
      request<any>("/scribe/addendum", {
        method: "POST",
        body: JSON.stringify({ encounter_id, addendum_text }),
      }),
  },

  claims: {
    scrub: (data: any) => request<any>("/claims/scrub", { method: "POST", body: JSON.stringify(data) }),
    list: (params?: { status?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set("status", params.status);
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      return request<{ claims: any[]; total: number }>(`/claims?${qs}`);
    },
    get: (id: string) => request<any>(`/claims/${id}`),
    override: (id: string, reason: string) =>
      request<any>(`/claims/${id}/override`, { method: "POST", body: JSON.stringify({ reason }), retries: 0 }),
    submit: (id: string) => request<any>(`/claims/${id}/submit`, { method: "POST", retries: 0 }),
    stats: () => request<any>("/claims/stats"),
  },

  discharge: {
    generate: (admission_id: string, patient_id: string) =>
      request<any>("/discharge/generate", {
        method: "POST",
        body: JSON.stringify({ admission_id, patient_id }),
        timeoutMs: 60000,
      }),
    get: (id: string) => request<any>(`/discharge/${id}`),
    updateStatus: (id: string, new_status: string) =>
      request<any>(`/discharge/${id}/status`, { method: "PUT", body: JSON.stringify({ new_status }), retries: 0 }),
    downloadPdf: async (id: string) => {
      const url = `${API_BASE}/discharge/${id}/pdf`;
      const res = await fetch(url, { headers: getAuthHeaders() });
      if (!res.ok) throw new ApiError("PDF download failed", res.status);
      return res.blob();
    },
  },

  sync: {
    clinicalNote: (qafya_encounter_id: string, soap_json: any) =>
      request<any>("/sync/clinical-note", {
        method: "POST",
        body: JSON.stringify({ qafya_encounter_id, soap_json }),
      }),
    dischargeSummary: (discharge_id: string) =>
      request<any>("/sync/discharge-summary", { method: "POST", body: JSON.stringify({ discharge_id }) }),
  },

  admin: {
    users: (limit = 50) => request<{ users: any[]; total: number }>(`/admin/users?limit=${limit}`),
    createUser: (data: any) => request<any>("/admin/users", { method: "POST", body: JSON.stringify(data), retries: 0 }),
    toggleUserStatus: (userId: string, is_active: boolean) =>
      request<any>(`/admin/users/${userId}/status`, {
        method: "PUT",
        body: JSON.stringify({ is_active }),
        retries: 0,
      }),
    auditLog: (params?: { limit?: number; offset?: number; action?: string }) => {
      const qs = new URLSearchParams();
      if (params?.limit) qs.set("limit", String(params.limit));
      if (params?.offset) qs.set("offset", String(params.offset));
      if (params?.action) qs.set("action", params.action);
      return request<{ logs: any[] }>(`/admin/audit-log?${qs}`);
    },
    syncStatus: () => request<any>("/admin/sync-status"),
  },

  health: () => request<any>("/health").catch(() => ({ status: "unreachable", components: {} })),
};

export { ApiError };
