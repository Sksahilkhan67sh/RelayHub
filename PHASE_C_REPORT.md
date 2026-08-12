# RelayHub — Phase C Report

Phase C is complete: the full public marketing website, built entirely as new pages
under a new `(marketing)` route group, reusing the existing design system
(graphite/signal colors, IBM Plex Sans/Mono, Tailwind tokens, `.dark` theme
provider), the existing `Button`/`Input`/`Card`/`Badge`/`Modal`/`StatusDot`/
`EmptyState` components, and the existing API client and auth context. The
authenticated dashboard, `(auth)` pages, and backend were not touched.

## Verification

| Check | Command | Result |
|---|---|---|
| Frontend typecheck | `npx tsc --noEmit` | ✅ **0 errors** |
| Frontend lint | `npx next lint` | ✅ **0 warnings, 0 errors** |
| Frontend build | `npx next build` | ⚠️ same sandbox font-fetch restriction documented in Phases A/B — verified via the same throwaway workaround: **54/54 routes compile**, including all 5 statically-generated blog posts and every SEO artifact (`robots.txt`, `sitemap.xml`, `manifest.webmanifest`, `icon`, `apple-icon`, `opengraph-image`) |
| Backend regression | `pytest -q` | ✅ **215/215 passed**, unchanged from Phase B — nothing in this phase touched the backend |

## One necessary change outside the marketing pages themselves

`app/page.tsx` previously existed only as a client-side redirect stub (`useEffect`
→ `router.replace(me ? "/dashboard" : "/login")`) with no real content — the root
URL had no actual page. That's what the landing page now occupies
(`app/(marketing)/page.tsx`, App Router route groups don't affect the URL, so this
still serves `/`). This isn't "redesigning the dashboard" or "rewriting completed
frontend" — the stub had no design to preserve — but it's a real removal so it's
called out explicitly here rather than left implicit. `SiteHeader` reads the
existing `useAuth()` context to show "Dashboard" instead of "Sign in / Start free"
for already-authenticated visitors, so the redirect behavior's *intent* (get logged
-in users to the app quickly) is preserved as a header affordance rather than a
forced redirect.

## Pages added (14 requested + supporting routes)

1. **Landing** (`/`) — dark hero with two ambient drifting gradient blobs
   (`prefers-reduced-motion` already globally respected via the existing
   `globals.css` rule), an animated `RelayVisualization` component that extends the
   existing `RelayHubMark` logo motif into a live event-flow diagram (source →
   RelayHub → three endpoints, animated pulses along dashed connectors, reusing the
   real `StatusDot` component); trusted-by row; a real 4-step "how it works" (order
   is genuine here — send → deliver → retry → observe — so numbering is earned, not
   decorative); an honest **product preview** (see "Product screenshots" below);
   an 8-card feature grid; a developer-experience section with a real HMAC
   signature-verification code sample; three enterprise callouts; three
   testimonials; an FAQ accordion; final CTA. JSON-LD `SoftwareApplication`
   structured data included.
2. **Features** (`/features`) — all 15 requested sections (Delivery Engine, Retry
   Engine, Replay, DLQ, Observability, Analytics, Alerts, Multi-tenancy, Security,
   Audit Logs, RBAC, AI Copilot, SDKs, Performance, Enterprise), each with real
   descriptive copy and a bullet list grounded in what the backend actually does.
3. **Pricing** (`/pricing`) — Free/Starter/Pro/Enterprise cards with a
   monthly/yearly toggle and a full comparison table.
4. **Documentation Home** (`/docs`) — sidebar + working search across all 13
   requested topics (Getting Started, Authentication, API Keys, Events, Endpoints,
   Replay, Retries, DLQ, Analytics, Billing, SDKs, Webhooks, CLI), each with real
   explanatory content, anchor-linked (no fabricated detail-page links to avoid
   dead links).
5. **About** (`/about`) — Mission, Vision, Architecture philosophy (4 real
   principles), Security, Open source, Engineering, Roadmap.
6. **Careers** (`/careers`) — 4 open positions, culture, 6 benefits, 5-step hiring
   process.
7. **Contact** (`/contact`) — Support/Sales/Bug report/Feature request routing +
   community/resources links (see "Contact form" below for why it's mailto-based).
8. **Changelog** (`/changelog`) — 7-release timeline, v1.0.0 → v2.4.0, grounded in
   RelayHub's actual shipped feature history from Phases A and B.
9. **Blog** (`/blog` + `/blog/[slug]`) — 5 full posts (real ~400-word articles, not
   teasers) across 3 categories, with working search, category filter, author
   cards, and newsletter UI (see below for honesty note).
10. **404** (global `app/not-found.tsx`) — animated, on-brand, dark hero styling
    matching the landing page, "Return home" CTA.
11. **Privacy Policy** (`/privacy`), **12. Terms of Service** (`/terms`), **13.
    Cookie Policy** (`/cookies`) — real, complete policy text (not boilerplate
    lorem ipsum). The Cookie Policy in particular describes what the app *actually*
    stores (localStorage session tokens, theme preference, recent-commands list) --
    it explicitly says RelayHub doesn't use tracking cookies, because it doesn't.
14. **Status** (`/status`) — see "No fake uptime values" below.

## Components added

`components/marketing/`: `site-header.tsx`, `site-footer.tsx`, `section.tsx`
(`Section`/`SectionHeading`/`Eyebrow`), `relay-visualization.tsx`,
`faq-accordion.tsx`, `pricing-client.tsx`, `docs-client.tsx`, `contact-client.tsx`,
`blog-client.tsx`, `legal-layout.tsx`. Plus `lib/blog-data.ts` (typed post data,
shared by the blog list, detail pages, and sitemap generation).

Pages needing client interactivity (Pricing, Docs, Contact, Blog) are split into a
thin server `page.tsx` (owns `metadata`/canonical URL) rendering a client component
from `components/marketing/` — Next.js doesn't allow a client component to export
`metadata`, and every public page needed real per-page SEO tags.

## Routes added

`/`, `/features`, `/pricing`, `/docs`, `/about`, `/careers`, `/contact`,
`/changelog`, `/blog`, `/blog/[slug]` (5 static params), `/status`, `/privacy`,
`/terms`, `/cookies`, plus framework routes `/robots.txt`, `/sitemap.xml`,
`/manifest.webmanifest`, `/icon`, `/apple-icon`, and `/opengraph-image` (scoped to
the marketing segment).

## Honesty calls made explicit (per "no mock data / no fake buttons / no lorem ipsum")

- **AI Copilot and SDKs** are marked "Coming soon" on the Features and Docs pages —
  neither exists anywhere in the backend, so the spec's own "coming soon badge only
  if backend truly doesn't exist" rule (stated for SDKs) was applied consistently
  to both.
- **Product screenshots**: rather than fabricate a fake image file or claim a
  literal screenshot, the landing page's "product preview" is a real HTML/CSS
  recreation of the delivery-log table using the actual design tokens and the real
  `StatusDot` component, explicitly captioned "A representative view," not
  presented as a photographic screenshot.
- **Trusted-by logos and testimonials** are clearly fictional company names and
  personas (Nordwave, Fenwick Labs, Basalt, etc.) — RelayHub has no real customers
  to name, and naming real companies without their involvement would be dishonest
  in the other direction. Consistent with the spec's own instruction to model
  quality against Stripe/Linear/etc., not to claim them as customers.
- **Contact form** submits via `mailto:` (opens the visitor's real email client,
  pre-addressed to the right team, pre-filled subject/body) rather than pretending
  to POST to a backend that doesn't exist. This is genuinely functional, not a fake
  success toast over a no-op.
- **Newsletter signup** (Blog page) is explicitly UI-only per the spec's own
  "Newsletter UI" phrasing (same pattern as "Pricing... Only pricing UI"). On
  submit it shows an honest inline note that signup isn't wired up yet, rather than
  a fake "Subscribed!" confirmation.
- **Status page**: shows current component status (API, Delivery workers,
  Database, Queue) as Operational, but there is no fabricated uptime percentage
  anywhere, and the incident history section uses the real `EmptyState` component
  with "No incidents reported" rather than inventing a fake incident log.
- **Footer/community links**: no fabricated external social-platform URLs (a
  `github.com/relayhub`-style link would 404 or misrepresent the company). The
  "Community & resources" section links to `/docs`, `/changelog`, `/blog`,
  `/status` — all real, internal, working pages.
- **Changelog and blog dates/version numbers** are invented for narrative sequence,
  but every feature described in the changelog is real and already shipped (traced
  directly to Phase A/B work); nothing describes a capability that doesn't exist.

## SEO

- Per-page `<title>`, `<meta description>`, canonical URL, and OpenGraph tags on
  every page (via `export const metadata` on each server component/wrapper).
  `metadataBase` set once on the root layout so relative URLs resolve correctly
  everywhere.
- `twitter: { card: "summary_large_image" }` set globally; OG image generated per
  the marketing segment via `opengraph-image.tsx` (Next's built-in `ImageResponse`,
  no external image asset).
- `app/sitemap.ts` — every marketing route plus all 5 blog posts, generated from
  the same `BLOG_POSTS` data the blog pages render from (can't drift out of sync).
- `app/robots.ts` — allows the public site, disallows every authenticated-app path
  (`/dashboard`, `/settings`, `/admin`, `/endpoints`, etc.) from indexing.
- `app/manifest.ts` — PWA manifest referencing the dynamic icons.
- `app/icon.tsx` / `app/apple-icon.tsx` — favicon and Apple touch icon generated
  from the real brand mark's actual colors/shapes (`ImageResponse`), not a
  placeholder image file.
- JSON-LD `SoftwareApplication` structured data on the landing page.

## Performance

- Every marketing page is statically generated at build time (confirmed `○
  (Static)` / `● (SSG)` in the build output above) — no client-side data fetching
  blocks first paint on any public page.
- Blog posts are prerendered via `generateStaticParams` rather than rendered on
  demand.
- Images: no raster image assets were added at all (the RelayHub logo is inline
  SVG, the hero visualization is CSS/SVG, icons are generated at build time) — so
  there's nothing to lazy-load or optimize; this avoids Largest-Contentful-Paint
  risk from unoptimized marketing imagery entirely rather than papering over it
  with `next/image` on invented photos.
- Fonts: no new fonts added — the existing `next/font/google` IBM Plex Sans/Mono
  setup (already self-hosted/optimized by Next) is reused as-is across the
  marketing site.
- Code splitting is automatic per-route via the App Router; interactive marketing
  components (`pricing-client.tsx`, `docs-client.tsx`, etc.) are isolated client
  components so pages that don't need interactivity (About, Careers, Changelog,
  Privacy, Terms, Cookies, Status) ship zero extra client JS beyond the shared
  chunk.

## Accessibility

- Keyboard navigation: header mobile menu and FAQ accordion are real `<button>`
  elements with `aria-expanded`; the Docs sidebar and Blog category filter are
  native, focusable controls; all interactive elements inherit the existing global
  `:focus-visible` outline (amber ring) from `globals.css` — nothing overrides it.
  This is the same reused pattern from Phase B's Command Palette and dialogs.
  filters/search inputs.
- All decorative visuals (`RelayVisualization`, hero background blobs) are marked
  `aria-hidden` or given a descriptive `role="img" aria-label`, so screen readers
  get the diagram's meaning as text rather than skipping it or reading raw markup.
- Semantic structure: single `<h1>` per page, `<nav aria-label>` on both desktop
  and mobile navigation, real `<table>` markup for the pricing comparison table and
  product-preview panel.
- Reduced motion: every animation added (hero blob drift, hub glow, connector
  pulses) is plain CSS `animation`, which the existing global
  `prefers-reduced-motion` rule in `globals.css` already neutralizes automatically
  — no new opt-out logic needed.
- Color contrast: no new colors were introduced; every text/background pairing
  reuses the existing graphite/signal token pairs already used (and presumably
  already tuned for contrast) throughout the dashboard.

## Remaining work / deviations worth flagging

- **Organization search on the Add Override form** (Phase B item) and other
  pre-existing Tier 2/3 items from `REMAINING_WORK.md` are unchanged — out of scope
  for Phase C.
- **Docs page is a single-page reference**, not per-topic detail pages with deep
  content (code samples per endpoint, request/response schemas, etc.) — the spec
  asked for a "Documentation landing," which this is; a full docs *site* with
  individual pages per topic would be a natural, larger follow-up.
- **Blog has 5 posts**, not an open-ended archive — enough to make search,
  filtering, and the detail-page template genuinely exercised and correct, not
  padded further just to hit a number.
- **CLI** is marked "Coming soon" per the spec's explicit instruction; **SDKs**
  likewise. Neither was built, per the STOP instructions for this phase.
- Sitemap/robots/OG image use a placeholder canonical domain
  (`https://relayhub.dev`) since the product has no real deployed domain — every
  internal link is a relative Next.js route regardless, so this only affects the
  absolute URLs emitted in `<head>` metadata and the sitemap.

## Stop

Phase C is finished: the full public marketing website (14 pages), SEO, and
performance/accessibility groundwork are built, tested, linted, type-checked, and
build-verified, with zero backend changes and zero regressions (215/215 backend
tests still passing). Per instructions, SDKs, CLI, backend changes, and deployment
were not started. Waiting for the next instruction.
