import type { Transport, RequestOptions } from "../transport.js";
import type { EventOut } from "../types.js";

export interface PublishEventParams {
  /** e.g. "payment.success" -- must match `<namespace>.<name>` in lowercase letters/digits/underscores. */
  event: string;
  payload?: Record<string, unknown>;
  environment?: "test" | "live";
  /**
   * Prefer `options.idempotencyKey` on the call itself (it sets this same field) --
   * both exist because the field is part of the real request body, not a header.
   */
  idempotency_key?: string;
}

export class EventsResource {
  constructor(private readonly transport: Transport) {}

  /**
   * POST /v1/events -- publishes an event, fanning it out to every endpoint
   * subscribed to `event` in the given environment. Pass `options.idempotencyKey`
   * to make republishing the same logical event safe to retry on your side.
   */
  publish(params: PublishEventParams, options?: RequestOptions) {
    return this.transport.request<EventOut>("POST", "/v1/events", params, options);
  }

  /** GET /v1/events/{id} */
  get(eventId: string, options?: RequestOptions) {
    return this.transport.request<EventOut>("GET", `/v1/events/${eventId}`, undefined, options);
  }

  /** GET /v1/events */
  list(options?: RequestOptions) {
    return this.transport.request<EventOut[]>("GET", "/v1/events", undefined, options);
  }
}
