// Event publishing example (Node.js SDK).
// Run: RELAYHUB_API_KEY=... node publish.mjs
//
// Requires the SDK to be built first: (cd ../../sdks/node && npm install && npm run build)
import { RelayHubClient } from "../../sdks/node/dist/index.js";

const apiKey = process.env.RELAYHUB_API_KEY;
if (!apiKey) {
  console.error("Set RELAYHUB_API_KEY (an API key with the events:write scope)");
  process.exit(1);
}

const client = new RelayHubClient({
  apiKey,
  baseUrl: process.env.RELAYHUB_BASE_URL,
});

const event = await client.events.publish(
  {
    event: "payment.success",
    environment: "test",
    payload: { order_id: "ord_123", amount: 4200 },
  },
  { idempotencyKey: "ord_123-payment-success" } // safe to retry this call with the same key
);

console.log(`Published ${event.event} -- event ${event.id}`);
console.log(`${event.delivery_jobs.length} delivery job(s) queued:`);
for (const job of event.delivery_jobs) {
  console.log(`  - ${job.id} -> endpoint ${job.endpoint_id} (${job.status})`);
}
