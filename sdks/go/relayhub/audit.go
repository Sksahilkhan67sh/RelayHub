package relayhub

import (
	"context"
	"strconv"
)

type AuditService struct{ t *transport }

// List calls GET /v1/audit-logs.
func (s *AuditService) List(ctx context.Context, limit, offset int, opts ...RequestOption) ([]AuditLog, error) {
	allOpts := opts
	if limit > 0 {
		allOpts = append(allOpts, WithQuery("limit", strconv.Itoa(limit)))
	}
	if offset > 0 {
		allOpts = append(allOpts, WithQuery("offset", strconv.Itoa(offset)))
	}
	return decode[[]AuditLog](s.t.do(ctx, "GET", "/v1/audit-logs", nil, allOpts...))
}
