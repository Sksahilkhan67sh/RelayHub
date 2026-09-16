"use client";

import { useState } from "react";
import { ShieldCheck, ShieldAlert, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, Badge } from "@/components/ui/card";

/**
 * Signature inspector.
 *
 * SECURITY: this is deliberately 100% client-side. The signing secret is never
 * sent to the RelayHub API, never persisted, and never logged -- it lives only
 * in React state for the lifetime of the page and is used exclusively as an
 * HMAC key via the browser's Web Crypto API.
 *
 * The signing contract implemented here mirrors
 * backend/app/modules/delivery/signing.py exactly:
 *
 *     signed_string = `${timestamp}.${nonce}.` + raw_body      (bytes)
 *     signature     = hex( HMAC_SHA256(secret, signed_string) )
 *
 * If that backend contract ever changes, this must change with it -- but note
 * the signing contract is treated as a frozen public API (changing it would
 * break every deployed customer verifier), so in practice it should not.
 */

const TOLERANCE_SECONDS = 300;

type Diagnosis = {
  ok: boolean;
  headline: string;
  details: string[];
};

function maskSignature(sig: string): string {
  // Show enough to eyeball a mismatch without printing a full credential-like
  // value into a screenshot or a support ticket.
  if (sig.length <= 12) return sig;
  return `${sig.slice(0, 8)}…${sig.slice(-4)} (${sig.length} chars)`;
}

async function computeSignature(secret: string, timestamp: string, nonce: string, rawBody: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signedString = encoder.encode(`${timestamp}.${nonce}.${rawBody}`);
  const buffer = await crypto.subtle.sign("HMAC", key, signedString);
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default function SignatureInspectorPage() {
  const [secret, setSecret] = useState("");
  const [timestamp, setTimestamp] = useState("");
  const [nonce, setNonce] = useState("");
  const [rawBody, setRawBody] = useState("");
  const [signature, setSignature] = useState("");
  const [result, setResult] = useState<Diagnosis | null>(null);
  const [busy, setBusy] = useState(false);

  async function verify() {
    setBusy(true);
    setResult(null);
    try {
      const details: string[] = [];

      // --- Structural checks first, so a developer gets the most specific
      // --- actionable reason rather than a generic "mismatch".
      if (!secret) {
        setResult({ ok: false, headline: "No signing secret provided", details: ["Paste the endpoint's signing secret to verify."] });
        return;
      }
      if (!/^\d+$/.test(timestamp.trim())) {
        setResult({
          ok: false,
          headline: "Invalid timestamp",
          details: [
            "X-RelayHub-Timestamp must be Unix seconds as an integer string.",
            `Received: ${JSON.stringify(timestamp)}`,
          ],
        });
        return;
      }
      if (!nonce.trim()) {
        setResult({
          ok: false,
          headline: "Missing nonce",
          details: ["X-RelayHub-Nonce is part of the signed string; verification cannot succeed without it."],
        });
        return;
      }
      const cleanedSignature = signature.trim().toLowerCase();
      if (!/^[0-9a-f]{64}$/.test(cleanedSignature)) {
        setResult({
          ok: false,
          headline: "Malformed signature",
          details: [
            "X-RelayHub-Signature must be a 64-character lowercase hex string (HMAC-SHA256).",
            `Received ${cleanedSignature.length} characters.`,
            cleanedSignature.startsWith("sha256=")
              ? "Hint: RelayHub does not prefix signatures with 'sha256=' — send the bare hex digest."
              : "",
          ].filter(Boolean),
        });
        return;
      }

      // --- Timestamp freshness (informational: a stale timestamp is a valid
      // --- signature that your verifier should still reject as a replay).
      const ageSeconds = Math.abs(Math.floor(Date.now() / 1000) - parseInt(timestamp, 10));
      if (ageSeconds > TOLERANCE_SECONDS) {
        details.push(
          `Timestamp is ${ageSeconds}s old, outside RelayHub's reference tolerance of ${TOLERANCE_SECONDS}s. ` +
            `A correct verifier should reject this as a possible replay even if the signature matches.`,
        );
      }

      const expected = await computeSignature(secret, timestamp.trim(), nonce.trim(), rawBody);

      if (expected === cleanedSignature) {
        setResult({
          ok: true,
          headline: "Signature is valid",
          details: [
            `Signed string: "${timestamp.trim()}.${nonce.trim()}." + raw body (${rawBody.length} bytes)`,
            ...details,
          ],
        });
      } else {
        setResult({
          ok: false,
          headline: "Signature mismatch",
          details: [
            `Expected: ${maskSignature(expected)}`,
            `Received: ${maskSignature(cleanedSignature)}`,
            "Most common cause: the raw body was re-serialized before verifying. RelayHub signs the exact bytes it sent — " +
              "verify against the raw request body, not a re-encoded JSON object (key order and whitespace both matter).",
            "Also check that the secret belongs to this endpoint, and that you are not verifying against a rotated/old secret.",
            ...details,
          ],
        });
      }
    } catch {
      setResult({
        ok: false,
        headline: "Could not compute signature",
        details: ["The browser's Web Crypto API rejected the input. This tool requires a secure context (HTTPS or localhost)."],
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Signature Inspector</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Verify a RelayHub webhook signature against the exact signing contract RelayHub uses.
        </p>
      </div>

      <Card className="flex gap-3 p-4">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-500" aria-hidden="true" />
        <div className="text-sm text-muted-foreground">
          <strong className="text-foreground">Your secret never leaves this browser.</strong> Verification runs entirely
          client-side using the Web Crypto API. Nothing on this page is sent to the RelayHub API, stored, or logged.
        </div>
      </Card>

      <Card className="space-y-4 p-6">
        <div>
          <label htmlFor="sig-secret" className="mb-1 block text-sm font-medium">
            Signing secret
          </label>
          <input
            id="sig-secret"
            type="password"
            autoComplete="off"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="whsec_…"
            className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="sig-timestamp" className="mb-1 block text-sm font-medium">
              X-RelayHub-Timestamp
            </label>
            <input
              id="sig-timestamp"
              value={timestamp}
              onChange={(e) => setTimestamp(e.target.value)}
              placeholder="1757923200"
              className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
            />
          </div>
          <div>
            <label htmlFor="sig-nonce" className="mb-1 block text-sm font-medium">
              X-RelayHub-Nonce
            </label>
            <input
              id="sig-nonce"
              value={nonce}
              onChange={(e) => setNonce(e.target.value)}
              placeholder="a1b2c3…"
              className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
            />
          </div>
        </div>

        <div>
          <label htmlFor="sig-signature" className="mb-1 block text-sm font-medium">
            X-RelayHub-Signature
          </label>
          <input
            id="sig-signature"
            value={signature}
            onChange={(e) => setSignature(e.target.value)}
            placeholder="64-character hex digest"
            className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
          />
        </div>

        <div>
          <label htmlFor="sig-body" className="mb-1 block text-sm font-medium">
            Raw request body
          </label>
          <textarea
            id="sig-body"
            value={rawBody}
            onChange={(e) => setRawBody(e.target.value)}
            rows={8}
            placeholder='{"event":"order.created","data":{}}'
            className="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Paste the exact bytes your server received. Re-serializing the JSON will change the signature.
          </p>
        </div>

        <Button onClick={verify} disabled={busy}>
          {busy ? "Verifying…" : "Verify signature"}
        </Button>
      </Card>

      {result && (
        <Card className="space-y-3 p-6">
          <div role="status" aria-live="polite" className="space-y-3">
          <div className="flex items-center gap-2">
            {result.ok ? (
              <ShieldCheck className="h-5 w-5 text-green-500" aria-hidden="true" />
            ) : (
              <ShieldAlert className="h-5 w-5 text-red-500" aria-hidden="true" />
            )}
            <h2 className="text-lg font-medium">{result.headline}</h2>
            <Badge tone={result.ok ? "green" : "red"}>{result.ok ? "valid" : "invalid"}</Badge>
          </div>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            {result.details.map((d, i) => (
              <li key={i} className="break-words">
                {d}
              </li>
            ))}
          </ul>
          </div>
        </Card>
      )}

      <Card className="space-y-2 p-6 text-sm text-muted-foreground">
        <h2 className="text-base font-medium text-foreground">The signing contract</h2>
        <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">
{`signed_string = "<timestamp>.<nonce>." + raw_body
signature     = hex(HMAC_SHA256(secret, signed_string))`}
        </pre>
        <p>
          Compare signatures in constant time (for example <code>hmac.compare_digest</code> in Python or{" "}
          <code>crypto.timingSafeEqual</code> in Node) — never with <code>==</code>.
        </p>
      </Card>
    </div>
  );
}
