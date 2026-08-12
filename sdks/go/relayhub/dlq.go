package relayhub

import (
	"context"
	"strconv"
)

type DLQService struct{ t *transport }

// List calls GET /v1/dlq -- deliveries that exhausted their retry budget.
func (s *DLQService) List(ctx context.Context, endpointID string, limit, offset int, opts ...RequestOption) ([]DeadLetterJob, error) {
	allOpts := opts
	if endpointID != "" {
		allOpts = append(allOpts, WithQuery("endpoint_id", endpointID))
	}
	if limit > 0 {
		allOpts = append(allOpts, WithQuery("limit", strconv.Itoa(limit)))
	}
	if offset > 0 {
		allOpts = append(allOpts, WithQuery("offset", strconv.Itoa(offset)))
	}
	return decode[[]DeadLetterJob](s.t.do(ctx, "GET", "/v1/dlq", nil, allOpts...))
}

// Get calls GET /v1/dlq/{jobId}.
func (s *DLQService) Get(ctx context.Context, jobID string, opts ...RequestOption) (DeadLetterJob, error) {
	return decode[DeadLetterJob](s.t.do(ctx, "GET", "/v1/dlq/"+jobID, nil, opts...))
}

// Retry calls POST /v1/dlq/{jobId}/retry -- replays a single dead-lettered
// delivery as a fresh attempt (same signed payload, doesn't re-trigger the
// source event). This is what "replay" means in the RelayHub API today: it's a
// DLQ operation, not a separate top-level /replay endpoint.
func (s *DLQService) Retry(ctx context.Context, jobID string, opts ...RequestOption) (RetryDeadLetterResponse, error) {
	return decode[RetryDeadLetterResponse](s.t.do(ctx, "POST", "/v1/dlq/"+jobID+"/retry", nil, opts...))
}

// BulkRetry calls POST /v1/dlq/bulk-retry -- replays up to 500 dead-lettered deliveries in one call.
func (s *DLQService) BulkRetry(ctx context.Context, jobIDs []string, opts ...RequestOption) (BulkRetryResponse, error) {
	body := map[string][]string{"job_ids": jobIDs}
	return decode[BulkRetryResponse](s.t.do(ctx, "POST", "/v1/dlq/bulk-retry", body, opts...))
}

// Discard calls DELETE /v1/dlq/{jobId} -- permanently discards a dead-lettered
// delivery without replaying it (204 No Content on success).
func (s *DLQService) Discard(ctx context.Context, jobID string, opts ...RequestOption) error {
	_, err := s.t.do(ctx, "DELETE", "/v1/dlq/"+jobID, nil, opts...)
	return err
}

// Export calls GET /v1/dlq/export -- CSV export; returns the raw text body.
func (s *DLQService) Export(ctx context.Context, endpointID string, opts ...RequestOption) (string, error) {
	allOpts := opts
	if endpointID != "" {
		allOpts = append(allOpts, WithQuery("endpoint_id", endpointID))
	}
	raw, err := s.t.do(ctx, "GET", "/v1/dlq/export", nil, allOpts...)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}
