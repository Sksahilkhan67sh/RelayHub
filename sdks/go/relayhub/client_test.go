package relayhub

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func newTestClient(t *testing.T, handler http.HandlerFunc) (*Client, *httptest.Server) {
	t.Helper()
	server := httptest.NewServer(handler)
	client := New("test_key", WithBaseURL(server.URL), WithClientMaxRetries(0))
	return client, server
}

func TestGetReturnsDecodedResponse(t *testing.T) {
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(Endpoint{ID: "ep_123", Name: "Test"})
	})
	defer server.Close()

	endpoint, err := client.Endpoints.Get(context.Background(), "ep_123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if endpoint.Name != "Test" {
		t.Errorf("expected Name=Test, got %q", endpoint.Name)
	}
}

func TestNotFoundMapsToError(t *testing.T) {
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(404)
		json.NewEncoder(w).Encode(map[string]any{"error": map[string]string{"message": "Endpoint not found", "code": "not_found"}})
	})
	defer server.Close()

	_, err := client.Endpoints.Get(context.Background(), "missing")
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !IsNotFound(err) {
		t.Errorf("expected IsNotFound(err) to be true, got false for %v", err)
	}
	rhErr := err.(*Error)
	if rhErr.Message != "Endpoint not found" {
		t.Errorf("expected message %q, got %q", "Endpoint not found", rhErr.Message)
	}
}

func TestRateLimitIsRetriedThenReturnsError(t *testing.T) {
	calls := 0
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Retry-After", "0")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(429)
		json.NewEncoder(w).Encode(map[string]any{"error": map[string]string{"message": "Too many requests"}})
	})
	defer server.Close()

	client = New("test_key", WithBaseURL(server.URL), WithClientMaxRetries(2))
	_, err := client.Endpoints.List(context.Background())
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !IsRateLimited(err) {
		t.Errorf("expected IsRateLimited(err) to be true")
	}
	if calls != 3 {
		t.Errorf("expected 3 calls (1 initial + 2 retries), got %d", calls)
	}
}

func TestServerErrorThenSuccessDoesNotFail(t *testing.T) {
	calls := 0
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		if calls == 1 {
			w.WriteHeader(500)
			json.NewEncoder(w).Encode(map[string]any{"error": map[string]string{"message": "boom"}})
			return
		}
		json.NewEncoder(w).Encode([]Endpoint{})
	})
	defer server.Close()

	client = New("test_key", WithBaseURL(server.URL), WithClientMaxRetries(2))
	result, err := client.Endpoints.List(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("expected empty slice, got %v", result)
	}
	if calls != 2 {
		t.Errorf("expected 2 calls, got %d", calls)
	}
}

func TestNoContentReturnsNoError(t *testing.T) {
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(204)
	})
	defer server.Close()

	if err := client.Auth.Logout(context.Background()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestIdempotencyKeySetsBodyField(t *testing.T) {
	var captured map[string]any
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		json.NewDecoder(r.Body).Decode(&captured)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(Event{ID: "evt_1", EventType: "payment.success"})
	})
	defer server.Close()

	_, err := client.Events.Publish(context.Background(), PublishEventRequest{Event: "payment.success"}, WithIdempotencyKey("order-42"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if captured["idempotency_key"] != "order-42" {
		t.Errorf("expected idempotency_key=order-42 in body, got %v", captured["idempotency_key"])
	}
}

func TestBuilderProducesWorkingClient(t *testing.T) {
	_, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(MeResponse{Role: "member"})
	})
	defer server.Close()

	client := NewBuilder().APIKey("test_key").BaseURL(server.URL).MaxRetries(0).Build()
	me, err := client.Auth.Me(context.Background())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if me.Role != "member" {
		t.Errorf("expected role=member, got %q", me.Role)
	}
}

func TestBuilderPanicsWithoutAPIKey(t *testing.T) {
	defer func() {
		if r := recover(); r == nil {
			t.Fatal("expected Build() to panic without an API key")
		}
	}()
	NewBuilder().Build()
}

func TestPerCallTimeoutOverride(t *testing.T) {
	client, server := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(50 * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode([]Endpoint{})
	})
	defer server.Close()

	_, err := client.Endpoints.List(context.Background(), WithTimeout(5*time.Millisecond), WithMaxRetries(0))
	if err == nil {
		t.Fatal("expected a timeout error, got nil")
	}
	if !IsConnectionError(err) {
		t.Errorf("expected IsConnectionError(err) to be true, got %v", err)
	}
}
