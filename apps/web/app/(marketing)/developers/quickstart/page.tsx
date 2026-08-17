import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { CodeTabs } from "@/components/marketing/code-tabs";

export const metadata: Metadata = {
  title: "Quickstart — RelayHub Developers",
  description: "Publish your first event and receive a verified webhook with RelayHub in about five minutes -- cURL, Node.js, and Python.",
  alternates: { canonical: "/developers/quickstart" },
  openGraph: {
    title: "RelayHub Quickstart",
    description: "Create credentials, publish an event, and verify a delivery -- in about five minutes.",
    url: "/developers/quickstart",
    type: "article",
  },
};

const STEPS = [
  { n: 1, label: "Create an account" },
  { n: 2, label: "Create an endpoint" },
  { n: 3, label: "Generate an API key" },
  { n: 4, label: "Publish an event" },
  { n: 5, label: "Verify the delivery" },
  { n: 6, label: "Inspect it" },
];

export default function QuickstartPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Quickstart</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
          Publish your first event in about five minutes
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Everything below is the real API -- every request shape, header, and response field matches what RelayHub
          actually sends and expects. No dashboard required until the last step.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          {STEPS.map((s) => (
            <span key={s.n} className="rounded-full border border-graphite-200 px-3 py-1 text-[11px] font-medium text-graphite-600 dark:border-graphite-700 dark:text-graphite-400">
              {s.n}. {s.label}
            </span>
          ))}
        </div>
      </Section>

      {/* Step 1 */}
      <Section className="py-10">
        <SectionHeading eyebrow="Step 1" title="Create an account" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Registering creates both your user account and your first organization in one call, and returns a session
          token you&apos;ll use for the next two steps.
        </p>
        <div className="mt-6">
          <CodeTabs
            filename="register"
            tabs={[
              {
                label: "cURL",
                code: `curl -X POST https://api.relayhub.dev/v1/auth/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "you@example.com",
    "password": "YOUR_SECRET",
    "full_name": "Your Name",
    "organization_name": "Your Company"
  }'

# -> { "access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900 }`,
              },
            ]}
          />
        </div>
        <p className="mt-3 text-xs text-graphite-500">Save the <code>access_token</code> -- you&apos;ll pass it as <code>Authorization: Bearer $TOKEN</code> for the next two steps.</p>
      </Section>

      {/* Step 2 */}
      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-10">
          <SectionHeading eyebrow="Step 2" title="Create an endpoint" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            An endpoint is a destination URL plus delivery configuration -- which event types it receives, a request
            timeout, and how many times to retry before giving up. Point it at a URL you control (or a request-bin
            service for testing).
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="create-endpoint"
              tabs={[
                {
                  label: "cURL",
                  code: `curl -X POST https://api.relayhub.dev/v1/endpoints \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{
    "name": "My first endpoint",
    "url": "https://your-app.example.com/webhooks/relayhub",
    "environment": "test",
    "subscribed_event_types": ["payment.success"],
    "max_retry_attempts": 5
  }'

# -> { "id": "YOUR_ENDPOINT_ID", "name": "My first endpoint", ... }`,
                },
              ]}
            />
          </div>
          <p className="mt-3 text-xs text-graphite-500">Leaving <code>subscribed_event_types</code> empty subscribes the endpoint to every event type -- explicit here for the example.</p>
        </Section>
      </div>

      {/* Step 3 */}
      <Section className="py-10">
        <SectionHeading eyebrow="Step 3" title="Generate an API key" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Publishing events uses an API key, not your session token -- a separate, scoped credential meant for
          server-to-server calls. The full key is shown exactly once, at creation.
        </p>
        <div className="mt-6">
          <CodeTabs
            filename="create-api-key"
            tabs={[
              {
                label: "cURL",
                code: `curl -X POST https://api.relayhub.dev/v1/api-keys \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{
    "name": "Quickstart key",
    "environment": "test"
  }'

# -> { "key": "YOUR_API_KEY", "key_prefix": "rh_test_...", "expires_at": null, ... }
# Store "key" now -- it is never retrievable again after this response.`,
              },
            ]}
          />
        </div>
      </Section>

      {/* Step 4 */}
      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-10">
          <SectionHeading eyebrow="Step 4" title="Publish an event" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            This is the call your application makes in production. The API key goes in its own header --{" "}
            <code>X-RelayHub-Api-Key</code>, not <code>Authorization</code>, which is reserved for user sessions like
            the one you used in steps 2 and 3.
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="publish"
              tabs={[
                {
                  label: "cURL",
                  code: `curl -X POST https://api.relayhub.dev/v1/events \\
  -H "X-RelayHub-Api-Key: YOUR_API_KEY" -H "Content-Type: application/json" \\
  -d '{
    "event": "payment.success",
    "payload": { "order_id": "ord_123", "amount": 4200 },
    "environment": "test"
  }'

# -> { "id": "...", "event": "payment.success", "delivery_jobs": [{ "id": "...", "endpoint_id": "YOUR_ENDPOINT_ID", "status": "queued" }] }`,
                },
                {
                  label: "Node.js",
                  code: `import { RelayHubClient } from "relayhub-sdk";

const client = new RelayHubClient({ apiKey: process.env.RELAYHUB_API_KEY! });

const result = await client.events.publish({
  event: "payment.success",
  payload: { order_id: "ord_123", amount: 4200 },
  environment: "test",
});

console.log(result.delivery_jobs);`,
                },
                {
                  label: "Python",
                  code: `from relayhub import RelayHubClient

client = RelayHubClient(api_key="YOUR_API_KEY")

result = client.events.publish(
    event="payment.success",
    payload={"order_id": "ord_123", "amount": 4200},
    environment="test",
)

print(result["delivery_jobs"])`,
                },
              ]}
            />
          </div>
          <p className="mt-3 text-xs text-graphite-500">
            The Node.js SDK is published (<code>npm install relayhub-sdk</code>). The Python SDK is fully tested but not
            yet published to PyPI -- install it from the <code>sdks/python</code> directory of the repository for now.
          </p>
        </Section>
      </div>

      {/* Step 5 */}
      <Section id="verify" className="scroll-mt-20 py-10">
        <SectionHeading eyebrow="Step 5" title="Verify the delivery on your side" />
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Every delivery is signed with HMAC-SHA256 over the timestamp, a nonce, and the raw body -- not the body
          alone, which is what makes the timestamp tamper-evident against replay. Verify it before trusting the
          payload.
        </p>
        <div className="mt-6">
          <CodeTabs
            filename="verify.js"
            tabs={[
              {
                label: "Node.js",
                code: `import { createHmac, timingSafeEqual } from "crypto";

// rawBody must be the exact bytes RelayHub sent -- a Buffer from your
// framework's raw-body middleware, not re-serialized parsed JSON.
function isValid(rawBody, headers, secret) {
  const signature = headers["x-relayhub-signature"];
  const timestamp = headers["x-relayhub-timestamp"];
  const nonce = headers["x-relayhub-nonce"];

  const signedString = \`\${timestamp}.\${nonce}.\` + rawBody;
  const expected = createHmac("sha256", secret).update(signedString).digest("hex");

  return timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
}`,
              },
            ]}
          />
        </div>
        <p className="mt-3 text-xs text-graphite-500">
          Get <code>YOUR_SECRET</code> for your endpoint from <code>POST /v1/endpoints/&#123;id&#125;/rotate-secret</code>
          -- see the <Link href="/docs#authentication" className="text-signal-amber hover:underline">Authentication</Link> docs.
        </p>
      </Section>

      {/* Step 6 */}
      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-10">
          <SectionHeading eyebrow="Step 6" title="Inspect the delivery" />
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Use the <code>id</code> from each entry in <code>delivery_jobs</code> (step 4&apos;s response) to pull the
            full attempt history -- status, HTTP response, latency, and retry state -- or open it directly in the
            dashboard&apos;s Deliveries page.
          </p>
          <div className="mt-6">
            <CodeTabs
              filename="inspect"
              tabs={[
                {
                  label: "cURL",
                  code: `curl https://api.relayhub.dev/v1/deliveries/YOUR_DELIVERY_JOB_ID \\
  -H "Authorization: Bearer $TOKEN"

# -> { "status": "success", "attempt_number": 1, "max_attempts": 5, "attempts": [...] }`,
                },
              ]}
            />
          </div>
        </Section>
      </div>

      <Section className="flex flex-col items-center gap-4 pb-24 pt-16 text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-graphite-950 dark:text-graphite-50">That&apos;s the whole loop.</h2>
        <p className="max-w-md text-[13.5px] text-graphite-600 dark:text-graphite-400">
          A non-2xx response or timeout on step 4 schedules a retry automatically -- no extra code needed.
        </p>
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          <Link href="/register">
            <Button size="md">
              Create Your First Endpoint
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
          <Link href="/docs">
            <Button variant="secondary" size="md">
              Read Documentation
            </Button>
          </Link>
        </div>
      </Section>
    </>
  );
}
