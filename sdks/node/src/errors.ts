export interface RelayHubErrorPayload {
  message: string;
  status: number;
  code?: string;
  requestId?: string;
  details?: unknown;
}

/** Base class for every error the SDK throws for a failed API call. */
export class RelayHubError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly requestId?: string;
  readonly details?: unknown;

  constructor(payload: RelayHubErrorPayload) {
    super(payload.message);
    this.name = "RelayHubError";
    this.status = payload.status;
    this.code = payload.code;
    this.requestId = payload.requestId;
    this.details = payload.details;
  }
}

/** 401 -- missing, invalid, or expired credentials. */
export class RelayHubAuthenticationError extends RelayHubError {
  constructor(payload: RelayHubErrorPayload) {
    super(payload);
    this.name = "RelayHubAuthenticationError";
  }
}

/** 403 -- authenticated, but the caller's role/API key scope doesn't allow this. */
export class RelayHubPermissionError extends RelayHubError {
  constructor(payload: RelayHubErrorPayload) {
    super(payload);
    this.name = "RelayHubPermissionError";
  }
}

/** 404. */
export class RelayHubNotFoundError extends RelayHubError {
  constructor(payload: RelayHubErrorPayload) {
    super(payload);
    this.name = "RelayHubNotFoundError";
  }
}

/** 409 -- conflicting state (duplicate invitation, already-revoked resource, etc). */
export class RelayHubConflictError extends RelayHubError {
  constructor(payload: RelayHubErrorPayload) {
    super(payload);
    this.name = "RelayHubConflictError";
  }
}

/** 422 / 400 -- request body or query params failed validation. */
export class RelayHubValidationError extends RelayHubError {
  constructor(payload: RelayHubErrorPayload) {
    super(payload);
    this.name = "RelayHubValidationError";
  }
}

/** 429 -- rate limited. `retryAfterSeconds` is set when the server sent Retry-After. */
export class RelayHubRateLimitError extends RelayHubError {
  readonly retryAfterSeconds?: number;

  constructor(payload: RelayHubErrorPayload & { retryAfterSeconds?: number }) {
    super(payload);
    this.name = "RelayHubRateLimitError";
    this.retryAfterSeconds = payload.retryAfterSeconds;
  }
}

/** 5xx from the API. */
export class RelayHubServerError extends RelayHubError {
  constructor(payload: RelayHubErrorPayload) {
    super(payload);
    this.name = "RelayHubServerError";
  }
}

/** The request never got a response: DNS failure, connection refused, or it hit the client-side timeout. */
export class RelayHubConnectionError extends RelayHubError {
  constructor(message: string, readonly cause?: unknown) {
    super({ message, status: 0 });
    this.name = "RelayHubConnectionError";
  }
}

export function errorForStatus(status: number, payload: RelayHubErrorPayload, retryAfterSeconds?: number): RelayHubError {
  if (status === 401) return new RelayHubAuthenticationError(payload);
  if (status === 403) return new RelayHubPermissionError(payload);
  if (status === 404) return new RelayHubNotFoundError(payload);
  if (status === 409) return new RelayHubConflictError(payload);
  if (status === 422 || status === 400) return new RelayHubValidationError(payload);
  if (status === 429) return new RelayHubRateLimitError({ ...payload, retryAfterSeconds });
  if (status >= 500) return new RelayHubServerError(payload);
  return new RelayHubError(payload);
}
