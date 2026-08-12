// Minimal webhook receiver: a plain Node http server (no framework dependency)
// that accepts a RelayHub delivery, verifies its signature against the raw
// request body, and responds 200 only if the signature is valid.
//
// Run: RELAYHUB_ENDPOINT_SECRET=<secret from POST /endpoints/{id}/rotate-secret> node server.mjs
// Then point a RelayHub endpoint's url at http://<this host>:8787/webhooks/relayhub

import { createServer } from "node:http";
import { createHmac, timingSafeEqual } from "node:crypto";

const PORT = process.env.PORT ? Number(process.env.PORT) : 8787;
const SECRET = process.env.RELAYHUB_ENDPOINT_SECRET;

if (!SECRET) {
  console.error("Set RELAYHUB_ENDPOINT_SECRET to the endpoint's signing secret.");
  process.exit(1);
}

function isValidSignature(rawBody, signatureHeader, secret) {
  if (!signatureHeader) return false;
  const expected = createHmac("sha256", secret).update(rawBody).digest("hex");
  const expectedBuf = Buffer.from(expected, "utf8");
  const providedBuf = Buffer.from(signatureHeader, "utf8");
  // timingSafeEqual throws if lengths differ -- check first to avoid that leaking info via a crash vs a false result.
  if (expectedBuf.length !== providedBuf.length) return false;
  return timingSafeEqual(expectedBuf, providedBuf);
}

const server = createServer((req, res) => {
  if (req.method !== "POST" || req.url !== "/webhooks/relayhub") {
    res.writeHead(404).end();
    return;
  }

  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    const rawBody = Buffer.concat(chunks);
    const signature = req.headers["x-relayhub-signature"];

    if (!isValidSignature(rawBody, signature, SECRET)) {
      console.warn("Rejected delivery: invalid signature");
      res.writeHead(401, { "Content-Type": "application/json" }).end(JSON.stringify({ error: "invalid signature" }));
      return;
    }

    const payload = JSON.parse(rawBody.toString("utf8"));
    console.log(`Received verified delivery: ${payload.event ?? "(unknown event)"}`);
    console.log(JSON.stringify(payload, null, 2));

    // Respond quickly with 2xx -- RelayHub records this as a successful attempt.
    // Do slow processing (DB writes, etc) after responding, not before.
    res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify({ received: true }));
  });
});

server.listen(PORT, () => {
  console.log(`Webhook receiver listening on http://localhost:${PORT}/webhooks/relayhub`);
});
