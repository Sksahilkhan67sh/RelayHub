package relayhub

import "fmt"

// Error is returned for every non-2xx response from the RelayHub API. Check
// Status or use the errors.Is-friendly Is* helpers below to branch on error kind.
type Error struct {
	Message        string
	Status         int
	Code           string
	RequestID      string
	Details        any
	RetryAfterSecs float64
	hasRetryAfter  bool
}

func (e *Error) Error() string {
	if e.Code != "" {
		return fmt.Sprintf("relayhub: %s (status=%d, code=%s)", e.Message, e.Status, e.Code)
	}
	return fmt.Sprintf("relayhub: %s (status=%d)", e.Message, e.Status)
}

// RetryAfter returns the server's Retry-After value (seconds) and whether one was sent.
func (e *Error) RetryAfter() (float64, bool) {
	return e.RetryAfterSecs, e.hasRetryAfter
}

// IsNotFound reports whether err is a 404 response from the API.
func IsNotFound(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status == 404
}

// IsAuthenticationError reports whether err is a 401 response.
func IsAuthenticationError(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status == 401
}

// IsPermissionError reports whether err is a 403 response.
func IsPermissionError(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status == 403
}

// IsConflict reports whether err is a 409 response.
func IsConflict(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status == 409
}

// IsValidationError reports whether err is a 400/422 response.
func IsValidationError(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && (rhErr.Status == 400 || rhErr.Status == 422)
}

// IsRateLimited reports whether err is a 429 response.
func IsRateLimited(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status == 429
}

// IsServerError reports whether err is a 5xx response.
func IsServerError(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status >= 500
}

// IsConnectionError reports whether the request never got a response at all
// (DNS failure, connection refused, or it hit the client-side timeout).
func IsConnectionError(err error) bool {
	rhErr, ok := err.(*Error)
	return ok && rhErr.Status == 0
}
