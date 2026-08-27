package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

/**
 * Typed response models mirroring the real Pydantic schemas in
 * backend/app/modules/*&#47;schemas.py. Nested under one class to keep the SDK's
 * file count manageable; each is a plain public-field DTO -- Jackson binds JSON
 * straight onto them via the SNAKE_CASE naming strategy configured in
 * {@link RelayHubClient}, so no per-field @JsonProperty annotations are needed.
 */
public final class Models {
    private Models() {}

    public static class User {
        public String id;
        public String email;
        public String fullName;
        public boolean isPlatformAdmin;
    }

    public static class Organization {
        public String id;
        public String name;
        public String slug;
    }

    public static class MeResponse {
        public User user;
        public Organization organization;
        public String role;
    }

    public static class TokenResponse {
        public String accessToken;
        public String refreshToken;
        public String tokenType;
    }

    public static class Member {
        public String userId;
        public String email;
        public String fullName;
        public String role;
        public String invitedByUserId;
        public String acceptedAt;
        public String joinedAt;
    }

    public static class Invitation {
        public String id;
        public String organizationId;
        public String email;
        public String role;
        public String invitedByUserId;
        public String status;
        public String expiresAt;
        public String acceptedAt;
        public String revokedAt;
        public String createdAt;
    }

    public static class InvitationPublic {
        public String organizationName;
        public String email;
        public String role;
        public String status;
        public String expiresAt;
    }

    public static class ApiKey {
        public String id;
        public String name;
        public String environment;
        public List<String> scopes;
        public String keyPrefix;
        public String maskedKey;
        public String lastUsedAt;
        public String expiresAt;
        public String revokedAt;
        public boolean isActive;
        public String createdAt;
    }

    /** Only ever returned once, at creation or rotation time -- {@code key} is never retrievable again. */
    public static class ApiKeyCreated {
        public String id;
        public String name;
        public String environment;
        public List<String> scopes;
        public String keyPrefix;
        public String key;
        public String expiresAt;
        public String createdAt;
    }

    public static class Endpoint {
        public String id;
        public String name;
        public String description;
        public String url;
        public String environment;
        public Map<String, String> customHeaders;
        public int timeoutSeconds;
        public List<String> subscribedEventTypes;
        public List<String> ipAllowlist;
        public boolean isActive;
        public boolean tlsVerificationEnabled;
        public Integer maxRetryAttempts;
        public String healthStatus;
        public int consecutiveFailureCount;
        public String lastSuccessAt;
        public String lastFailureAt;
        public String pausedAt;
        public String pausedReason;
        public String createdAt;
    }

    public static class EndpointSecret {
        public String id;
        public String secret;
        public String gracePeriodEndsAt;
        public String createdAt;
    }

    public static class DeliveryJobSummary {
        public String id;
        public String endpointId;
        public String status;
    }

    public static class Event {
        public String id;
        public String event;
        public String environment;
        public Map<String, Object> payload;
        public String requestId;
        public String createdAt;
        public List<DeliveryJobSummary> deliveryJobs;
    }

    public static class DeliveryAttempt {
        public String id;
        public int attemptNumber;
        public String status;
        public Integer responseStatusCode;
        public Integer latencyMs;
        public String errorCategory;
        public String errorMessage;
        public String attemptedAt;
    }

    public static class DeliveryJob {
        public String id;
        public String eventId;
        public String endpointId;
        public String status;
        public int attemptNumber;
        public String queuedAt;
        public String nextAttemptAt;
        public String completedAt;
        public List<DeliveryAttempt> attempts;
    }

    public static class DeliveryLogEntry {
        public String id;
        public String eventId;
        public String endpointId;
        public String eventType;
        public String environment;
        public String requestId;
        public String status;
        public int attemptNumber;
        public String queuedAt;
        public String nextAttemptAt;
        public String completedAt;
        public List<DeliveryAttempt> attempts;
    }

    public static class DeadLetterJob {
        public String id;
        public String eventId;
        public String endpointId;
        public String eventType;
        public Map<String, Object> payload;
        public int attemptNumber;
        public String queuedAt;
        public String completedAt;
        public String lastErrorCategory;
        public String lastErrorMessage;
        public List<DeliveryAttempt> attempts;
    }

    public static class RetryDeadLetterResponse {
        public String id;
        public String status;
    }

    public static class BulkRetryResponse {
        public List<String> retried;
        public List<String> skipped;
    }

    public static class Summary {
        public int totalEvents;
        public int totalDeliveries;
        public double successRate;
        public Double p50LatencyMs;
        public Double p95LatencyMs;
        public Double p99LatencyMs;
    }

    public static class TimeSeriesBucket {
        public String bucket;
        public int successCount;
        public int failureCount;
    }

    public static class EventTypeVolume {
        public String eventType;
        public int count;
    }

    public static class TopEndpoint {
        public String endpointId;
        public String endpointName;
        public int deliveryCount;
        public double failureRate;
    }

    public static class EndpointHealth {
        public String endpointId;
        public String endpointName;
        public String healthStatus;
        public int consecutiveFailureCount;
    }

    public static class Plan {
        public String id;
        public String tier;
        public String name;
        public int priceCents;
        public Integer maxDeliveriesPerMonth;
        public Integer maxEndpoints;
        public int logRetentionDays;
        public int rateLimitPerMinute;
        public int rateLimitPerHour;
        public int rateLimitPerDay;
        public boolean allowOverage;
        public boolean hasAdvancedAnalytics;
        public boolean hasPrioritySupport;
        public boolean hasSso;
    }

    public static class Subscription {
        public String id;
        public Plan plan;
        public String status;
        public String currentPeriodStart;
        public String currentPeriodEnd;
        public String trialEnd;
        public boolean cancelAtPeriodEnd;
    }

    public static class Usage {
        public String periodStart;
        public String periodEnd;
        public int deliveryCount;
        public Integer maxDeliveriesPerMonth;
        public Double percentUsed;
        public int endpointCount;
        public Integer maxEndpoints;
    }

    public static class Invoice {
        public String id;
        public String stripeInvoiceId;
        public int amountCents;
        public String status;
        public String invoicePdfUrl;
        public String periodStart;
        public String periodEnd;
        public String createdAt;
    }

    public static class CheckoutSession {
        public String checkoutUrl;
    }

    public static class PortalSession {
        public String portalUrl;
    }

    /** "Notifications" in RelayHub's product surface are alert rules -- see NotificationsResource. */
    public static class AlertRule {
        public String id;
        public String conditionType;
        public String severity;
        public String channel;
        public Map<String, Object> channelConfig;
        public Map<String, Object> thresholdConfig;
        public int throttleWindowMinutes;
        public boolean isEnabled;
        public String createdAt;
    }

    public static class AlertEvent {
        public String id;
        public String conditionType;
        public String severity;
        public String message;
        public String resourceId;
        public String deliveryStatus;
        public String deliveryError;
        public String triggeredAt;
        public String deliveredAt;
    }

    public static class TestAlertResponse {
        public String deliveryStatus;
        public String deliveryError;
    }

    public static class AuditLog {
        public String id;
        public String actorUserId;
        public String action;
        public String resourceType;
        public String resourceId;
        public Map<String, Object> metadata;
        public String ipAddress;
        public String createdAt;
    }

    /** Mirrors backend/app/modules/insights/schemas.py::EndpointHealthSnapshotOut. */
    public static class EndpointHealthSnapshot {
        public String id;
        public String endpointId;
        public String windowStart;
        public String windowEnd;
        public String status;
        public Double healthScore;
        public double confidence;
        public int sampleSize;
        public Double successRate;
        public Double failureRate;
        public Double http4xxRate;
        public Double http5xxRate;
        public Double timeoutRate;
        public Double retryRate;
        public Double dlqRate;
        public Double latencyP50Ms;
        public Double latencyP95Ms;
        public Map<String, Object> supportingSignals;
    }

    public static class InsightAnomaly {
        public String id;
        public String endpointId;
        public String metric;
        public String direction;
        public double observedValue;
        public double baselineValue;
        public double delta;
        public String observedAt;
        public double confidence;
        public int sampleSize;
        public List<Object> evidence;
        public String incidentId;
    }

    /** {@code source} is "deterministic" or "ai" -- keep this distinction visible in anything built on top of this type. */
    public static class RootCauseAnalysis {
        public String id;
        public String source;
        public String likelyCause;
        public String confidenceLevel;
        public double confidenceScore;
        public List<Object> evidence;
        public List<String> recommendations;
        public String aiProvider;
        public String aiModel;
        public String createdAt;
    }

    public static class Incident {
        public String id;
        public String endpointId;
        public String status;
        public String failureCategory;
        public String severity;
        public String title;
        public String summary;
        public String openedAt;
        public String recoveringSince;
        public String resolvedAt;
        public String lastSignalAt;
    }

    public static class IncidentDetail extends Incident {
        public List<InsightAnomaly> anomalies;
        public List<RootCauseAnalysis> rcaEntries;
    }

    public static class Recommendations {
        public String incidentId;
        public List<String> recommendations;
    }

    public static class IncidentTimelineEvent {
        public String type;
        public String at;
        public String detail;
    }

    public static class IncidentTimeline {
        public String incidentId;
        public String status;
        public List<IncidentTimelineEvent> events;
    }
}
