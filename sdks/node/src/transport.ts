import { errorForStatus, RelayHubConnectionError, type RelayHubErrorPayload } from "./errors.js";

export interface RequestOptions {
  query?: Record<string, string | number | boolean | string[] | undefined>;
  headers?: Record<string, string>;
  /** Overrides the client's default timeout for this call only. */
  timeoutMs?: number;
  /** Overrides the client's default retry count for this call only. */
  maxRetries?: number;
  /** Sets the `idempotency_key` field RelayHub's publish-event endpoint accepts in its body (see PublishEventRequest). */
  idempotencyKey?: string;
}

export interface TransportConfig {
  baseUrl: string;
  apiKey: string;
  timeoutMs: number;
  maxRetries: number;
  defaultHeaders: Record<string, string>;
  fetchImpl?: typeof fetch;
}

const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);

function buildQueryString(query?: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      for (const v of value) params.append(key, String(v));
    } else {
      params.append(key, String(value));
    }
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Low-level HTTP transport shared by every resource client. Handles auth headers,
 * timeouts (via AbortController), exponential-backoff retries on 429/5xx and
 * network errors, and mapping non-2xx responses to typed RelayHubError subclasses.
 * Not exported from the package root -- resources are the public surface.
 */
export class Transport {
  constructor(private readonly config: TransportConfig) {}

  async request<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
    const url = `${this.config.baseUrl}${path}${buildQueryString(options.query)}`;
    const maxRetries = options.maxRetries ?? this.config.maxRetries;
    const timeoutMs = options.timeoutMs ?? this.config.timeoutMs;
    const fetchImpl = this.config.fetchImpl ?? fetch;

    const requestBody: unknown =
      options.idempotencyKey && body && typeof body === "object" ? { ...(body as object), idempotency_key: options.idempotencyKey } : body;

    let attempt = 0;
    for (;;) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetchImpl(url, {
          method,
          signal: controller.signal,
          headers: {
            // The backend's API-key auth dependency (app/modules/api_keys/dependencies.py)
            // reads ONLY this header -- Authorization: Bearer is reserved for dashboard user
            // JWT sessions (app/modules/auth/dependencies.py), a completely separate auth
            // path. Sending Authorization here (as this transport did until this fix) means
            // every request 401s against the real backend with "Missing X-RelayHub-Api-Key
            // header", regardless of how valid the key is.
            "X-RelayHub-Api-Key": this.config.apiKey,
            "Content-Type": "application/json",
            "User-Agent": "relayhub-node/1.0.0",
            ...this.config.defaultHeaders,
            ...options.headers,
          },
          body: requestBody !== undefined ? JSON.stringify(requestBody) : undefined,
        });

        if (response.status === 204) return undefined as T;

        const isJson = response.headers.get("content-type")?.includes("application/json");
        const data = isJson ? await response.json() : await response.text();

        if (response.ok) return data as T;

        const retryAfterHeader = response.headers.get("retry-after");
        const retryAfterSeconds = retryAfterHeader ? Number(retryAfterHeader) : undefined;

        if (RETRYABLE_STATUS.has(response.status) && attempt < maxRetries) {
          attempt++;
          await sleep(backoffMs(attempt, retryAfterSeconds));
          continue;
        }

        const payload: RelayHubErrorPayload = extractErrorPayload(data, response.status);
        throw errorForStatus(response.status, payload, retryAfterSeconds);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          if (attempt < maxRetries) {
            attempt++;
            await sleep(backoffMs(attempt));
            continue;
          }
          throw new RelayHubConnectionError(`Request to ${path} timed out after ${timeoutMs}ms`, err);
        }
        if (isRelayHubError(err)) throw err;
        if (attempt < maxRetries) {
          attempt++;
          await sleep(backoffMs(attempt));
          continue;
        }
        throw new RelayHubConnectionError(`Request to ${path} failed: ${(err as Error).message}`, err);
      } finally {
        clearTimeout(timer);
      }
    }
  }
}

function backoffMs(attempt: number, retryAfterSeconds?: number): number {
  if (retryAfterSeconds !== undefined && !Number.isNaN(retryAfterSeconds)) return retryAfterSeconds * 1000;
  const base = Math.min(1000 * 2 ** (attempt - 1), 8000);
  const jitter = Math.random() * 250;
  return base + jitter;
}

function extractErrorPayload(data: unknown, status: number): RelayHubErrorPayload {
  if (data && typeof data === "object" && "error" in data) {
    const err = (data as { error?: { message?: string; code?: string; request_id?: string } }).error;
    return { message: err?.message ?? "Request failed", status, code: err?.code, requestId: err?.request_id, details: data };
  }
  if (typeof data === "string" && data) return { message: data, status };
  return { message: `Request failed with status ${status}`, status, details: data };
}

function isRelayHubError(err: unknown): boolean {
  return !!err && typeof err === "object" && "status" in (err as object) && "name" in (err as object) && String((err as Error).name).startsWith("RelayHub");
}
