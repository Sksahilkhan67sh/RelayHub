package dev.relayhub.sdk;

/** Base class for every exception the SDK throws for a failed API call. */
public class RelayHubException extends RuntimeException {
    private final int status;
    private final String code;
    private final String requestId;
    private final Object details;
    private final Double retryAfterSeconds;

    public RelayHubException(String message, int status, String code, String requestId, Object details, Double retryAfterSeconds) {
        super(message);
        this.status = status;
        this.code = code;
        this.requestId = requestId;
        this.details = details;
        this.retryAfterSeconds = retryAfterSeconds;
    }

    public int getStatus() { return status; }
    public String getCode() { return code; }
    public String getRequestId() { return requestId; }
    public Object getDetails() { return details; }

    /** Non-null only for {@link RateLimitException}, when the server sent a Retry-After header. */
    public Double getRetryAfterSeconds() { return retryAfterSeconds; }

    /** 401 -- missing, invalid, or expired credentials. */
    public static class AuthenticationException extends RelayHubException {
        public AuthenticationException(String message, int status, String code, String requestId, Object details) {
            super(message, status, code, requestId, details, null);
        }
    }

    /** 403 -- authenticated, but the caller's role/API key scope doesn't allow this. */
    public static class PermissionException extends RelayHubException {
        public PermissionException(String message, int status, String code, String requestId, Object details) {
            super(message, status, code, requestId, details, null);
        }
    }

    /** 404. */
    public static class NotFoundException extends RelayHubException {
        public NotFoundException(String message, int status, String code, String requestId, Object details) {
            super(message, status, code, requestId, details, null);
        }
    }

    /** 409 -- conflicting state (duplicate invitation, already-revoked resource, etc). */
    public static class ConflictException extends RelayHubException {
        public ConflictException(String message, int status, String code, String requestId, Object details) {
            super(message, status, code, requestId, details, null);
        }
    }

    /** 422 / 400 -- request body or query params failed validation. */
    public static class ValidationException extends RelayHubException {
        public ValidationException(String message, int status, String code, String requestId, Object details) {
            super(message, status, code, requestId, details, null);
        }
    }

    /** 429 -- rate limited. {@link #getRetryAfterSeconds()} is set when the server sent Retry-After. */
    public static class RateLimitException extends RelayHubException {
        public RateLimitException(String message, int status, String code, String requestId, Object details, Double retryAfterSeconds) {
            super(message, status, code, requestId, details, retryAfterSeconds);
        }
    }

    /** 5xx from the API. */
    public static class ServerException extends RelayHubException {
        public ServerException(String message, int status, String code, String requestId, Object details) {
            super(message, status, code, requestId, details, null);
        }
    }

    /** The request never got a response: DNS failure, connection refused, or it hit the client-side timeout. */
    public static class ConnectionException extends RelayHubException {
        public ConnectionException(String message, Throwable cause) {
            super(message, 0, null, null, null, null);
            if (cause != null) initCause(cause);
        }
    }

    static RelayHubException forStatus(int status, String message, String code, String requestId, Object details, Double retryAfterSeconds) {
        switch (status) {
            case 401: return new AuthenticationException(message, status, code, requestId, details);
            case 403: return new PermissionException(message, status, code, requestId, details);
            case 404: return new NotFoundException(message, status, code, requestId, details);
            case 409: return new ConflictException(message, status, code, requestId, details);
            case 400:
            case 422: return new ValidationException(message, status, code, requestId, details);
            case 429: return new RateLimitException(message, status, code, requestId, details, retryAfterSeconds);
            default:
                if (status >= 500) return new ServerException(message, status, code, requestId, details);
                return new RelayHubException(message, status, code, requestId, details, retryAfterSeconds);
        }
    }
}
