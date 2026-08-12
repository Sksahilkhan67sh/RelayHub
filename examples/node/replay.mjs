// Delivery replay example (Node.js SDK).
// Run: RELAYHUB_API_KEY=<session-derived-or-management-key> node replay.mjs [jobId]
//
// If no jobId is given, replays the first dead-lettered job found.
import { RelayHubClient } from "../../sdks/node/dist/index.js";

const apiKey = process.env.RELAYHUB_API_KEY;
if (!apiKey) {
  console.error("Set RELAYHUB_API_KEY");
  process.exit(1);
}

const client = new RelayHubClient({ apiKey, baseUrl: process.env.RELAYHUB_BASE_URL });

const targetId = process.argv[2];

if (targetId) {
  const result = await client.dlq.retry(targetId);
  console.log(`Replayed ${targetId} -- new status: ${result.status}`);
} else {
  const jobs = await client.dlq.list({ limit: 1 });
  if (jobs.length === 0) {
    console.log("Nothing in the dead-letter queue.");
    process.exit(0);
  }
  const job = jobs[0];
  console.log(`Replaying ${job.id} (${job.event_type} -> endpoint ${job.endpoint_id})`);
  console.log(`Last error: ${job.last_error_message ?? "(none recorded)"}`);
  const result = await client.dlq.retry(job.id);
  console.log(`New status: ${result.status}`);
}
