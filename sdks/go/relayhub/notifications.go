package relayhub

import "context"

// NotificationsService maps to RelayHub's alert rules: Slack, Discord, webhook,
// or email notifications fired when an endpoint's failure rate crosses a
// threshold. There is no separate /notifications API in the backend -- this
// service is named for the developer-facing concept it serves, while every
// method below hits the real /v1/alerts/* routes.
type NotificationsService struct{ t *transport }

type CreateAlertRuleRequest struct {
	ConditionType         string         `json:"condition_type"`
	Severity              string         `json:"severity,omitempty"`
	Channel               string         `json:"channel"`
	ChannelConfig         map[string]any `json:"channel_config"`
	ThresholdConfig       map[string]any `json:"threshold_config,omitempty"`
	ThrottleWindowMinutes *int           `json:"throttle_window_minutes,omitempty"`
	IsEnabled             *bool          `json:"is_enabled,omitempty"`
}

// CreateRule calls POST /v1/alerts/rules.
func (s *NotificationsService) CreateRule(ctx context.Context, req CreateAlertRuleRequest, opts ...RequestOption) (AlertRule, error) {
	return decode[AlertRule](s.t.do(ctx, "POST", "/v1/alerts/rules", req, opts...))
}

// ListRules calls GET /v1/alerts/rules.
func (s *NotificationsService) ListRules(ctx context.Context, opts ...RequestOption) ([]AlertRule, error) {
	return decode[[]AlertRule](s.t.do(ctx, "GET", "/v1/alerts/rules", nil, opts...))
}

type UpdateAlertRuleRequest struct {
	Severity              string         `json:"severity,omitempty"`
	Channel               string         `json:"channel,omitempty"`
	ChannelConfig         map[string]any `json:"channel_config,omitempty"`
	ThresholdConfig       map[string]any `json:"threshold_config,omitempty"`
	ThrottleWindowMinutes *int           `json:"throttle_window_minutes,omitempty"`
	IsEnabled             *bool          `json:"is_enabled,omitempty"`
}

// UpdateRule calls PATCH /v1/alerts/rules/{id}.
func (s *NotificationsService) UpdateRule(ctx context.Context, ruleID string, req UpdateAlertRuleRequest, opts ...RequestOption) (AlertRule, error) {
	return decode[AlertRule](s.t.do(ctx, "PATCH", "/v1/alerts/rules/"+ruleID, req, opts...))
}

// DeleteRule calls DELETE /v1/alerts/rules/{id} (204 No Content on success).
func (s *NotificationsService) DeleteRule(ctx context.Context, ruleID string, opts ...RequestOption) error {
	_, err := s.t.do(ctx, "DELETE", "/v1/alerts/rules/"+ruleID, nil, opts...)
	return err
}

// TestRule calls POST /v1/alerts/rules/{id}/test -- fires a test notification through the rule's configured channel.
func (s *NotificationsService) TestRule(ctx context.Context, ruleID string, opts ...RequestOption) (TestAlertResponse, error) {
	return decode[TestAlertResponse](s.t.do(ctx, "POST", "/v1/alerts/rules/"+ruleID+"/test", nil, opts...))
}

// History calls GET /v1/alerts/history.
func (s *NotificationsService) History(ctx context.Context, conditionType string, opts ...RequestOption) ([]AlertEvent, error) {
	allOpts := opts
	if conditionType != "" {
		allOpts = append(allOpts, WithQuery("condition_type", conditionType))
	}
	return decode[[]AlertEvent](s.t.do(ctx, "GET", "/v1/alerts/history", nil, allOpts...))
}
