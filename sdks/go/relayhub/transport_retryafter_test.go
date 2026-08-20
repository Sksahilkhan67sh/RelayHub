package relayhub

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"
	"time"
)

// Regression test: Retry-After must REPLACE exponential backoff for that wait,
// not stack with it. Before the fix, a 429 with Retry-After: 2 would sleep 2s
// for Retry-After AND then ALSO sleep ~1s of exponential backoff on the next
// loop iteration, wasting time beyond what the server actually asked for.
func TestRetryAfterDoesNotStackWithExponentialBackoff(t *testing.T) {
	calls := 0
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls == 1 {
			w.Header().Set("Retry-After", "2")
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(429)
			json.NewEncoder(w).Encode(map[string]any{"error": map[string]string{"message": "Too many requests"}})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		json.NewEncoder(w).Encode([]any{})
	})
	defer server.Close()

	client = New("test_key", WithBaseURL(server.URL), WithClientMaxRetries(1))

	start := time.Now()
	_, err := client.Endpoints.List(context.Background())
	elapsed := time.Since(start)

	if err != nil {
		t.Fatalf("expected success on retry, got error: %v", err)
	}
	// Should wait ~2s (the Retry-After value) and NOT an additional ~1-8s of
	// exponential backoff on top. Allow generous margin for CI jitter/scheduling,
	// but a stacked-sleep regression would push this well past 3s.
	if elapsed < 1900*time.Millisecond {
		t.Errorf("expected wait of at least ~2s (Retry-After), got %v", elapsed)
	}
	if elapsed > 3200*time.Millisecond {
		t.Errorf("expected wait of ~2s (Retry-After only, no stacked backoff), got %v -- looks like Retry-After stacked with exponential backoff", elapsed)
	}
}
