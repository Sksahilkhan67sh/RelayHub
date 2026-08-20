package relayhub

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"math/rand"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

var retryableStatus = map[int]bool{429: true, 500: true, 502: true, 503: true, 504: true}

// requestOptions carries per-call overrides. Zero value means "use client defaults."
type requestOptions struct {
	query          url.Values
	headers        map[string]string
	timeout        time.Duration
	maxRetries     *int
	idempotencyKey string
}

// RequestOption customizes a single SDK call, e.g. client.Endpoints.List(ctx, WithTimeout(2*time.Second)).
type RequestOption func(*requestOptions)

// WithQuery adds/overrides a query parameter for this call.
func WithQuery(key, value string) RequestOption {
	return func(o *requestOptions) {
		if o.query == nil {
			o.query = url.Values{}
		}
		o.query.Set(key, value)
	}
}

// WithHeader adds a custom header for this call.
func WithHeader(key, value string) RequestOption {
	return func(o *requestOptions) {
		if o.headers == nil {
			o.headers = map[string]string{}
		}
		o.headers[key] = value
	}
}

// WithTimeout overrides the client's default timeout for this call only.
func WithTimeout(d time.Duration) RequestOption {
	return func(o *requestOptions) { o.timeout = d }
}

// WithMaxRetries overrides the client's default retry count for this call only.
func WithMaxRetries(n int) RequestOption {
	return func(o *requestOptions) { o.maxRetries = &n }
}

// WithIdempotencyKey sets the `idempotency_key` field RelayHub's publish-event
// endpoint accepts in its body (a real body field, not a header -- see docs/api/events.md).
func WithIdempotencyKey(key string) RequestOption {
	return func(o *requestOptions) { o.idempotencyKey = key }
}

type transport struct {
	baseURL        string
	apiKey         string
	timeout        time.Duration
	maxRetries     int
	defaultHeaders map[string]string
	httpClient     *http.Client
}

func (t *transport) do(ctx context.Context, method, path string, body any, opts ...RequestOption) (json.RawMessage, error) {
	options := &requestOptions{}
	for _, opt := range opts {
		opt(options)
	}

	maxRetries := t.maxRetries
	if options.maxRetries != nil {
		maxRetries = *options.maxRetries
	}
	timeout := t.timeout
	if options.timeout > 0 {
		timeout = options.timeout
	}

	fullURL := t.baseURL + path
	if len(options.query) > 0 {
		fullURL += "?" + options.query.Encode()
	}

	var bodyBytes []byte
	if body != nil {
		payload := body
		if options.idempotencyKey != "" {
			payload = mergeIdempotencyKey(body, options.idempotencyKey)
		}
		encoded, err := json.Marshal(payload)
		if err != nil {
			return nil, fmt.Errorf("relayhub: failed to encode request body: %w", err)
		}
		bodyBytes = encoded
	}

	var lastErr error
	for attempt := 0; attempt <= maxRetries; attempt++ {
		callCtx, cancel := context.WithTimeout(ctx, timeout)
		req, err := http.NewRequestWithContext(callCtx, method, fullURL, bytes.NewReader(bodyBytes))
		if err != nil {
			cancel()
			return nil, fmt.Errorf("relayhub: failed to build request: %w", err)
		}
		// See the matching comment in the Node SDK's transport.ts -- the backend's
		// API-key auth dependency (app/modules/api_keys/dependencies.py) reads ONLY
		// this header. Authorization: Bearer is reserved for dashboard user JWT
		// sessions, a separate auth path this client never uses.
		req.Header.Set("X-RelayHub-Api-Key", t.apiKey)
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("User-Agent", "relayhub-go/1.0.1")
		for k, v := range t.defaultHeaders {
			req.Header.Set(k, v)
		}
		for k, v := range options.headers {
			req.Header.Set(k, v)
		}

		resp, err := t.httpClient.Do(req)
		cancel()
		if err != nil {
			lastErr = &Error{Message: fmt.Sprintf("request to %s failed: %v", path, err), Status: 0}
			if attempt < maxRetries {
				time.Sleep(backoff(attempt + 1))
				continue
			}
			return nil, lastErr
		}

		respBody, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if readErr != nil {
			lastErr = &Error{Message: fmt.Sprintf("failed to read response from %s: %v", path, readErr), Status: 0}
			if attempt < maxRetries {
				time.Sleep(backoff(attempt + 1))
				continue
			}
			return nil, lastErr
		}

		if resp.StatusCode == 204 {
			return nil, nil
		}

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return respBody, nil
		}

		retryAfterSecs, hasRetryAfter := parseRetryAfter(resp.Header.Get("Retry-After"))

		if retryableStatus[resp.StatusCode] && attempt < maxRetries {
			// Retry-After, when the server sends it, REPLACES our own exponential
			// backoff for this wait -- it should never stack with it. Falling back
			// to backoff only when the server didn't tell us how long to wait.
			if hasRetryAfter {
				time.Sleep(time.Duration(retryAfterSecs * float64(time.Second)))
			} else {
				time.Sleep(backoff(attempt + 1))
			}
			continue
		}

		return nil, errorFromBody(resp.StatusCode, respBody, retryAfterSecs, hasRetryAfter)
	}

	return nil, lastErr
}

func mergeIdempotencyKey(body any, key string) map[string]any {
	encoded, err := json.Marshal(body)
	if err != nil {
		return map[string]any{"idempotency_key": key}
	}
	var m map[string]any
	if err := json.Unmarshal(encoded, &m); err != nil || m == nil {
		m = map[string]any{}
	}
	m["idempotency_key"] = key
	return m
}

func backoff(attempt int) time.Duration {
	shifted := 1 << uint(attempt-1)
	base := math.Min(float64(shifted), 8.0)
	jitter := rand.Float64() * 0.25
	return time.Duration((base + jitter) * float64(time.Second))
}

func parseRetryAfter(header string) (float64, bool) {
	if header == "" {
		return 0, false
	}
	seconds, err := strconv.ParseFloat(header, 64)
	if err != nil {
		return 0, false
	}
	return seconds, true
}

type errorEnvelope struct {
	Error struct {
		Message   string `json:"message"`
		Code      string `json:"code"`
		RequestID string `json:"request_id"`
	} `json:"error"`
}

func errorFromBody(status int, body []byte, retryAfterSecs float64, hasRetryAfter bool) *Error {
	var env errorEnvelope
	message := fmt.Sprintf("request failed with status %d", status)
	code := ""
	requestID := ""
	if err := json.Unmarshal(body, &env); err == nil && env.Error.Message != "" {
		message = env.Error.Message
		code = env.Error.Code
		requestID = env.Error.RequestID
	} else if trimmed := strings.TrimSpace(string(body)); trimmed != "" {
		message = trimmed
	}
	return &Error{
		Message:        message,
		Status:         status,
		Code:           code,
		RequestID:      requestID,
		Details:        string(body),
		RetryAfterSecs: retryAfterSecs,
		hasRetryAfter:  hasRetryAfter,
	}
}

func decode[T any](raw json.RawMessage, err error) (T, error) {
	var zero T
	if err != nil {
		return zero, err
	}
	if raw == nil {
		return zero, nil
	}
	var out T
	if unmarshalErr := json.Unmarshal(raw, &out); unmarshalErr != nil {
		return zero, fmt.Errorf("relayhub: failed to decode response: %w", unmarshalErr)
	}
	return out, nil
}
