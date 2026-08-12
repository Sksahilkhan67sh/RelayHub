package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

/**
 * "Notifications" maps to RelayHub's alert rules: Slack, Discord, webhook, or
 * email notifications fired when an endpoint's failure rate crosses a threshold.
 * There is no separate /notifications API in the backend -- this resource is
 * named for the developer-facing concept it serves, while every method below
 * hits the real /v1/alerts/* routes.
 */
public final class NotificationsResource {
    private final Transport transport;

    NotificationsResource(Transport transport) { this.transport = transport; }

    public static final class CreateAlertRuleRequest {
        public String conditionType;
        public String severity = "warning";
        public String channel;
        public Map<String, Object> channelConfig;
        public Map<String, Object> thresholdConfig;
        public Integer throttleWindowMinutes;
        public Boolean isEnabled = true;

        public CreateAlertRuleRequest(String conditionType, String channel, Map<String, Object> channelConfig) {
            this.conditionType = conditionType; this.channel = channel; this.channelConfig = channelConfig;
        }
    }

    /** POST /v1/alerts/rules */
    public Models.AlertRule createRule(CreateAlertRuleRequest req) { return createRule(req, null); }
    public Models.AlertRule createRule(CreateAlertRuleRequest req, RequestOptions options) {
        return transport.request("POST", "/v1/alerts/rules", req, Models.AlertRule.class, options);
    }

    /** GET /v1/alerts/rules */
    public List<Models.AlertRule> listRules() { return listRules(null); }
    public List<Models.AlertRule> listRules(RequestOptions options) {
        return transport.requestList("GET", "/v1/alerts/rules", null, Models.AlertRule.class, options);
    }

    public static final class UpdateAlertRuleRequest {
        public String severity;
        public String channel;
        public Map<String, Object> channelConfig;
        public Map<String, Object> thresholdConfig;
        public Integer throttleWindowMinutes;
        public Boolean isEnabled;
    }

    /** PATCH /v1/alerts/rules/{id} */
    public Models.AlertRule updateRule(String ruleId, UpdateAlertRuleRequest req) { return updateRule(ruleId, req, null); }
    public Models.AlertRule updateRule(String ruleId, UpdateAlertRuleRequest req, RequestOptions options) {
        return transport.request("PATCH", "/v1/alerts/rules/" + ruleId, req, Models.AlertRule.class, options);
    }

    /** DELETE /v1/alerts/rules/{id} -- 204 No Content on success. */
    public void deleteRule(String ruleId) { deleteRule(ruleId, null); }
    public void deleteRule(String ruleId, RequestOptions options) {
        transport.request("DELETE", "/v1/alerts/rules/" + ruleId, null, Void.class, options);
    }

    /** POST /v1/alerts/rules/{id}/test -- fires a test notification through the rule's configured channel. */
    public Models.TestAlertResponse testRule(String ruleId) { return testRule(ruleId, null); }
    public Models.TestAlertResponse testRule(String ruleId, RequestOptions options) {
        return transport.request("POST", "/v1/alerts/rules/" + ruleId + "/test", null, Models.TestAlertResponse.class, options);
    }

    /** GET /v1/alerts/history */
    public List<Models.AlertEvent> history(String conditionType) { return history(conditionType, null); }
    public List<Models.AlertEvent> history(String conditionType, RequestOptions options) {
        RequestOptions.Builder b = RequestOptions.builder();
        if (options != null) { options.headers.forEach(b::header); options.query.forEach(b::query); }
        if (conditionType != null) b.query("condition_type", conditionType);
        return transport.requestList("GET", "/v1/alerts/history", null, Models.AlertEvent.class, b.build());
    }
}
