/**
 * Typed fetch wrapper for the RelayHub API.
 *
 * Token storage note: access/refresh tokens are kept in localStorage for this build.
 * That's a real, documented tradeoff (XSS risk vs. httpOnly-cookie complexity), not
 * an oversight -- a hardening pass wiring this through Next.js Route Handlers as a
 * BFF (setting httpOnly cookies instead) is listed in the README's remaining work
 * alongside the other security-hardening items already flagged in this build.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiErrorShape {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: unknown;
  };
}

export class ApiError extends Error {
  code: string;
  status: number;
  requestId: string | null;
  details?: unknown;

  constructor(status: number, body: ApiErrorShape) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.status = status;
    this.requestId = body.error.request_id;
    this.details = body.error.details;
  }
}

const TOKEN_KEY = "relayhub_access_token";
const REFRESH_KEY = "relayhub_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  window.localStorage.setItem(TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  skipAuth?: boolean;
  skipRefreshRetry?: boolean;
  headers?: Record<string, string>;
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const resp = await fetch(`${API_BASE_URL}/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!resp.ok) {
    clearTokens();
    return false;
  }
  const data = await resp.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false, skipRefreshRetry = false, headers: extraHeaders } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json", ...extraHeaders };
  if (!skipAuth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 401 && !skipAuth && !skipRefreshRetry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, { ...options, skipRefreshRetry: true });
    }
  }

  if (resp.status === 204) {
    return undefined as T;
  }

  const contentType = resp.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await resp.json() : await resp.text();

  if (!resp.ok) {
    if (isJson && data?.error) {
      throw new ApiError(resp.status, data as ApiErrorShape);
    }
    throw new ApiError(resp.status, {
      error: { code: "unknown_error", message: typeof data === "string" ? data : "Request failed", request_id: null },
    });
  }

  return data as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
