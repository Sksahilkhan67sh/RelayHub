import { Transport, type TransportConfig } from "./transport.js";
import { AuthResource } from "./resources/auth.js";
import { ApiKeysResource } from "./resources/api-keys.js";
import { OrganizationsResource } from "./resources/organizations.js";
import { EndpointsResource } from "./resources/endpoints.js";
import { EventsResource } from "./resources/events.js";
import { DeliveriesResource } from "./resources/deliveries.js";
import { DlqResource } from "./resources/dlq.js";
import { AnalyticsResource } from "./resources/analytics.js";
import { BillingResource } from "./resources/billing.js";
import { NotificationsResource } from "./resources/notifications.js";
import { AuditResource } from "./resources/audit.js";

export interface RelayHubClientConfig {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
  defaultHeaders?: Record<string, string>;
  fetch?: typeof fetch;
}

const DEFAULT_BASE_URL = "https://api.relayhub.dev/v1";
const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_MAX_RETRIES = 2;

export class RelayHubClient {
  readonly auth: AuthResource;
  readonly apiKeys: ApiKeysResource;
  readonly organizations: OrganizationsResource;
  readonly endpoints: EndpointsResource;
  readonly events: EventsResource;
  readonly deliveries: DeliveriesResource;
  readonly dlq: DlqResource;
  readonly analytics: AnalyticsResource;
  readonly billing: BillingResource;
  readonly notifications: NotificationsResource;
  readonly audit: AuditResource;

  constructor(config: RelayHubClientConfig) {
    if (!config.apiKey) throw new Error("RelayHubClient requires an apiKey");

    // baseUrl carries "/v1" so resource paths below can use the literal API paths
    // (e.g. "/v1/endpoints") as documented in the API reference and RELEASE_CHECKLIST.md.
    const baseUrl = (config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/v1\/?$/, "").replace(/\/$/, "");

    const transportConfig: TransportConfig = {
      baseUrl,
      apiKey: config.apiKey,
      timeoutMs: config.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      maxRetries: config.maxRetries ?? DEFAULT_MAX_RETRIES,
      defaultHeaders: config.defaultHeaders ?? {},
      fetchImpl: config.fetch,
    };
    const transport = new Transport(transportConfig);

    this.auth = new AuthResource(transport);
    this.apiKeys = new ApiKeysResource(transport);
    this.organizations = new OrganizationsResource(transport);
    this.endpoints = new EndpointsResource(transport);
    this.events = new EventsResource(transport);
    this.deliveries = new DeliveriesResource(transport);
    this.dlq = new DlqResource(transport);
    this.analytics = new AnalyticsResource(transport);
    this.billing = new BillingResource(transport);
    this.notifications = new NotificationsResource(transport);
    this.audit = new AuditResource(transport);
  }

  static builder(): RelayHubClientBuilder {
    return new RelayHubClientBuilder();
  }
}

/**
 * Fluent alternative to the config-object constructor, for callers who prefer it
 * or are assembling config conditionally:
 *
 *   const client = RelayHubClient.builder()
 *     .apiKey(process.env.RELAYHUB_API_KEY!)
 *     .baseUrl("https://api.relayhub.dev/v1")
 *     .timeout(10_000)
 *     .maxRetries(3)
 *     .header("X-Client-Name", "checkout-service")
 *     .build();
 */
export class RelayHubClientBuilder {
  private config: Partial<RelayHubClientConfig> = {};

  apiKey(apiKey: string): this {
    this.config.apiKey = apiKey;
    return this;
  }

  baseUrl(baseUrl: string): this {
    this.config.baseUrl = baseUrl;
    return this;
  }

  timeout(timeoutMs: number): this {
    this.config.timeoutMs = timeoutMs;
    return this;
  }

  maxRetries(maxRetries: number): this {
    this.config.maxRetries = maxRetries;
    return this;
  }

  header(name: string, value: string): this {
    this.config.defaultHeaders = { ...this.config.defaultHeaders, [name]: value };
    return this;
  }

  fetchImpl(fetchFn: typeof fetch): this {
    this.config.fetch = fetchFn;
    return this;
  }

  build(): RelayHubClient {
    if (!this.config.apiKey) throw new Error("RelayHubClientBuilder: apiKey(...) is required before build()");
    return new RelayHubClient(this.config as RelayHubClientConfig);
  }
}
