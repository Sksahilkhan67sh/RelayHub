export interface BlogAuthor {
  name: string;
  role: string;
}

export interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  category: "Reliability" | "Engineering" | "Security";
  author: BlogAuthor;
  date: string;
  readMinutes: number;
  body: string[];
}

export const AUTHORS = {
  dana: { name: "Dana Whitfield", role: "Engineering" },
  sana: { name: "Sana Iqbal", role: "Engineering" },
  marcus: { name: "Marcus Oyelaran", role: "Developer Relations" },
} satisfies Record<string, BlogAuthor>;

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: "fire-and-forget-webhooks-fail",
    title: "Why \"fire and forget\" webhooks fail in production",
    excerpt: "A single HTTP call with no retry policy works fine in a demo. It fails silently the first time a partner's endpoint has a bad five minutes.",
    category: "Reliability",
    author: AUTHORS.dana,
    date: "July 28, 2026",
    readMinutes: 5,
    body: [
      "Most webhook senders start the same way: an event happens, you make an HTTP POST to the subscriber's URL, and if it returns a 200 you move on. It works in a demo. It works in the first month of production. Then a partner's endpoint has a deploy that takes their service down for four minutes, and every event you sent during that window is gone -- not queued, not retried, just gone.",
      "The failure mode isn't dramatic. Nobody gets paged. The delivery just returns a 502 or times out, your fire-and-forget call logs an error nobody reads, and the loop moves on to the next event. Weeks later, a support ticket comes in: \"we never got notified about that refund.\" Now someone is grepping application logs trying to reconstruct what happened, with no delivery record to start from.",
      "The fix isn't complicated in concept -- retry on failure, with backoff, up to a bounded number of attempts -- but it's exactly the kind of infrastructure that's tedious to build well and easy to get subtly wrong. A fixed retry interval hammers a struggling endpoint instead of giving it room to recover. No maximum attempt count means a permanently broken endpoint retries forever, burning your delivery workers on a lost cause. And without per-attempt logging, you're back to reconstructing history from scraps.",
      "This is the entire reason RelayHub's retry engine exists: exponential backoff by default, a configurable cap per endpoint, and every attempt -- successful or not -- written to a log you can actually search. The goal isn't to make failures impossible. It's to make sure a failure is visible, bounded, and recoverable, instead of a silent gap in your delivery history.",
    ],
  },
  {
    slug: "practical-guide-exponential-backoff",
    title: "A practical guide to exponential backoff",
    excerpt: "Backoff sounds simple until you're the one setting the base interval, the multiplier, and the cap for a real endpoint with real traffic.",
    category: "Engineering",
    author: AUTHORS.dana,
    date: "June 12, 2026",
    readMinutes: 6,
    body: [
      "Exponential backoff is one of those ideas that sounds trivial in a sentence -- \"wait longer between each retry\" -- and gets genuinely fiddly the moment you have to pick real numbers for a real system. Too aggressive a base interval, and you're hammering a recovering endpoint right as it comes back up. Too conservative, and a transient blip turns into a ten-minute delivery delay for something time-sensitive.",
      "RelayHub's default schedule doubles the wait after each failed attempt, starting at a short interval and capping at a configurable maximum -- so attempt two might be seconds away, but attempt five is minutes away, not hours. That shape matters: most failures are transient (a deploy, a brief network blip, a cold start) and resolve within the first couple of retries. The backoff schedule should get out of the way quickly for those, and only really start spacing things out once it's clear something more persistent is going on.",
      "The other half of the equation is the attempt cap. An endpoint that's been down for two days doesn't need RelayHub quietly retrying against it forever -- that's wasted work, and it delays the moment you actually notice something is wrong. Once the cap is hit, the delivery moves to the dead-letter queue: visible, inspectable, and one click from being replayed the moment the endpoint is fixed.",
      "If you're building this yourself: log every attempt with its scheduled time and outcome from day one. The backoff curve is easy to get right in isolation and easy to get subtly wrong under real traffic patterns -- you'll want the data to tune it later, not just the code to run it now.",
    ],
  },
  {
    slug: "how-we-built-the-dead-letter-queue",
    title: "How we built RelayHub's dead-letter queue",
    excerpt: "A DLQ that nobody looks at is just a more expensive way to drop events. Here's how we designed ours to actually get used.",
    category: "Engineering",
    author: AUTHORS.sana,
    date: "May 3, 2026",
    readMinutes: 7,
    body: [
      "A dead-letter queue is an easy feature to build badly. The minimum viable version is: a table where failed deliveries go once they run out of retries. That's technically a DLQ, and it's also functionally a graveyard -- if there's no good way to search it, filter it, or act on what's in it, it accumulates rows nobody ever looks at until someone's debugging an incident and discovers it exists.",
      "We designed RelayHub's DLQ around the question we actually wanted to answer when we opened it during an incident: \"what failed, for which endpoint, and can I fix it right now?\" That meant the DLQ needed to be filterable by endpoint and event type from the start, not bolted on later. It meant every dead-lettered delivery needed to retain its full payload and its complete attempt history -- not just the final failure, but what happened on attempt one, two, and three, since the pattern of failures is often the fastest way to diagnose the actual cause.",
      "The other design decision that mattered: replay had to be a first-class action, not an afterthought. Once you've fixed whatever was broken on the receiving end, re-sending a dead-lettered delivery should be one click, and it should behave exactly like a normal retry -- signed the same way, logged the same way -- so there's no special case to reason about.",
      "The result is boring in the best way: the DLQ is just another filtered view into the same delivery log, with a replay button. No separate system, no separate mental model. That turned out to be the right call -- the less special the failure path is, the more likely people are to actually use it.",
    ],
  },
  {
    slug: "verifying-webhook-signatures-checklist",
    title: "Verifying webhook signatures: a checklist",
    excerpt: "Signature verification is four lines of code and a surprisingly common source of security bugs. Here's what to actually check.",
    category: "Security",
    author: AUTHORS.marcus,
    date: "March 19, 2026",
    readMinutes: 4,
    body: [
      "Every webhook platform worth using signs its payloads, and every integration guide tells you to verify the signature before trusting the request. What the guides don't always cover is the handful of ways that verification code quietly stops actually protecting anything.",
      "First: use a constant-time comparison. Comparing the computed and received signatures with a plain string equality check leaks timing information about how many leading characters matched, which is a real (if slow) attack vector. Use your language's constant-time comparison function -- Node's timingSafeEqual, Python's hmac.compare_digest -- not ==.",
      "Second: verify against the raw request body, not a re-serialized version of the parsed JSON. If your framework parses the body before your verification code runs, and you re-serialize it to compute the signature, whitespace or key-ordering differences between the original bytes and your re-serialization will break verification in ways that are maddening to debug and tempting to just disable.",
      "Third: check the timestamp, if the platform includes one, and reject requests outside a reasonable window. Signature verification alone proves the payload wasn't tampered with -- it doesn't prove the request isn't a replay of a legitimate one captured earlier. A timestamp check closes that gap.",
      "Fourth: fail closed. If the signature header is missing, malformed, or doesn't match, reject the request before it touches any business logic -- don't log a warning and process it anyway. It's tempting during initial integration testing to leave verification 'soft' so you can debug faster; that's exactly the kind of temporary code that ends up shipping.",
    ],
  },
  {
    slug: "designing-rbac-for-multi-tenant-api",
    title: "Designing RBAC for a multi-tenant API",
    excerpt: "Four roles, enforced at the route level, audited on every change -- how we thought about access control for organizations with real teams.",
    category: "Engineering",
    author: AUTHORS.dana,
    date: "February 14, 2026",
    readMinutes: 6,
    body: [
      "The instinct when you're a two-person team is to skip roles entirely -- everyone with an account has full access, because everyone is trusted and there's no one to restrict. That model breaks the moment an organization brings on a support contractor who needs to read delivery logs but shouldn't be able to rotate a signing secret, or a finance person who needs billing access and nothing else.",
      "We settled on four roles -- owner, admin, member, viewer -- because that was the smallest set that covered the real distinctions organizations kept asking for: full control, operational control without billing/ownership transfer, day-to-day usage, and read-only access. More granular permission systems are more flexible in theory, but in practice they push a configuration burden onto every organization that most teams never actually want to carry.",
      "The part that mattered more than the role list itself was where enforcement lives. It would have been faster to check roles in the UI and call it done, but that's not access control, that's a suggestion. Every route that mutates or reads sensitive data checks the caller's role server-side, independent of what the frontend happens to show. The dashboard hiding a button is a UX nicety; the API rejecting the request is the actual security boundary.",
      "The last piece was making role changes themselves accountable: every membership and role change is written to the audit log with who did it, when, and from where. Access control that can be changed invisibly isn't much better than no access control -- the audit trail is what makes the roles trustworthy after the fact, not just at the moment they're checked.",
    ],
  },
];

export function getPostBySlug(slug: string): BlogPost | undefined {
  return BLOG_POSTS.find((p) => p.slug === slug);
}
