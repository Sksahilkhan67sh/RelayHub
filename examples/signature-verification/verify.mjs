// Standalone signature verification -- no server required. Useful for testing
// against a captured payload, or for languages/frameworks not covered by the
// full webhook-receiver example.
import { createHmac, timingSafeEqual } from "node:crypto";

export function verifyRelayHubSignature(rawBody, signatureHeader, secret) {
  const expected = createHmac("sha256", secret).update(rawBody).digest("hex");
  const expectedBuf = Buffer.from(expected, "utf8");
  const providedBuf = Buffer.from(signatureHeader ?? "", "utf8");
  if (expectedBuf.length !== providedBuf.length) return false;
  return timingSafeEqual(expectedBuf, providedBuf);
}

// Self-test when run directly: node verify.mjs
if (import.meta.url === `file://${process.argv[1]}`) {
  const secret = "test_secret_123";
  const body = JSON.stringify({ event: "payment.success", payload: { order_id: "ord_123" } });
  const validSig = createHmac("sha256", secret).update(body).digest("hex");

  console.log("Valid signature accepted:", verifyRelayHubSignature(body, validSig, secret) === true);
  console.log("Tampered body rejected:", verifyRelayHubSignature(body + "x", validSig, secret) === false);
  console.log("Wrong secret rejected:", verifyRelayHubSignature(body, validSig, "wrong_secret") === false);
}
