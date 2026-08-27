# Phase 5C Completion Report — SEO Optimization

## Scope

Close the evidence-based gaps found in `PHASE_5C_SEO_AUDIT.md` in the
existing marketing-site SEO system (`apps/web/app/(marketing)`). No
redesign, no URL changes, no backend changes, no new SEO library.

## Scope source

`PHASE_5C_SEO_AUDIT.md`, produced by auditing the attached repo. The
marketing site already had titles, descriptions, canonicals, robots.txt,
and a dynamic sitemap from prior phases — Phase 5C targeted only what was
missing or wrong.

## Architecture

No new dependencies. Uses Next.js 14 App Router native primitives already
in use elsewhere in the repo: `Metadata` exports, `next/og`'s
`ImageResponse` for the OG image, and root-`<head>` JSON-LD `<script>`
tags (matching the pattern the homepage already used).

## Implementation

### Backend
None. No SEO gap required a backend change.

### Frontend

| File | Change |
|---|---|
| `app/opengraph-image.tsx` (new) | Dynamic OG/Twitter image generator (`next/og`), real brand colors/copy from the homepage hero and `tailwind.config.ts` — not a static placeholder. Next.js auto-wires this as `og:image` and `twitter:image` for every page that doesn't define its own. |
| `app/layout.tsx` | Added site-wide `Organization` + `WebSite` JSON-LD in `<head>`, using the real production domain and existing `logo.png`. |
| `app/(marketing)/page.tsx` | Fixed the homepage's `SoftwareApplication` JSON-LD, which claimed a flat `"price": "0"` — misrepresenting the real Starter ($29) / Pro ($99) tiers. Replaced with an `AggregateOffer` (`lowPrice: 0`, `highPrice: 99`, `offerCount: 3`) sourced from `components/marketing/pricing-client.tsx`. Enterprise (custom-quoted) is excluded rather than assigned a fabricated number. |
| `app/(marketing)/blog/[slug]/page.tsx` | Added `Article` JSON-LD built only from fields the API actually returns (`title`, `excerpt`, `category`, `author_name`, `published_at`/`created_at`, `updated_at` when it differs). No invented author, dates, or image. |
| `app/(marketing)/terms/page.tsx`, `.../cookies/page.tsx`, `.../privacy/page.tsx` | Added the `openGraph` block these 3 pages were missing (23/26 pages already had it). |
| `app/robots.ts` | Fixed a real gap found during the audit: the disallow list covered every `(dashboard)` route except `/intelligence`. Added it. |
| `middleware.ts` (new) | Sends `X-Robots-Tag: noindex, nofollow` on the same authenticated-route list as `robots.ts`. robots.txt only stops a compliant crawler from *choosing* to crawl a path; it does nothing if that URL is discovered another way (e.g. linked externally). The header blocks indexing of the response itself regardless of how it was found. |

### Database / API / AI / Workers / SDKs / CLI
No changes — none were required by the confirmed scope.

## Security

No authentication, RBAC, or tenant-isolation code touched. The one
security-adjacent change (`middleware.ts`) is additive and narrowly
scoped: it only ever *adds* a response header on a fixed allowlist of
already-authenticated route prefixes; it does not alter access control.

## Observability

Not touched — out of scope.

## Tests

No dedicated SEO test suite exists in the repo, and none of the master
prompt's own definition-of-done items required inventing one from
scratch for a metadata/markup-only change of this size. Verification was
done via the compiler/linter (below) plus manual review of the generated
JSON-LD structure and the middleware's route matcher against `robots.ts`.

## Verification

| Check | Command | Result |
|---|---|---|
| TypeScript | `npx tsc --noEmit` | ✅ PASS — no errors |
| Lint | `npm run lint` | ✅ PASS — "No ESLint warnings or errors" |
| Production build | `npm run build` | ⚠️ **UNVERIFIED — ENVIRONMENT LIMITATION**. Fails at the font-loading step (`next/font/google` tries to fetch `fonts.googleapis.com`, which isn't reachable from this sandbox's network allowlist). This is unrelated to any Phase 5C change — the same fonts (`IBM Plex Sans`/`Mono`) were already configured in `layout.tsx` before this phase. |
| Runtime smoke test (`/robots.txt`, `/sitemap.xml`, live page requests) | — | **UNVERIFIED — ENVIRONMENT LIMITATION**, same network restriction; `next dev`/`next start` need the same font fetch. |
| Backend regression | — | Not run. No backend file was modified this phase, so there's no backend change to regress. |

## Known limitations

- Production build and a live crawl couldn't be executed in this
  environment because outbound access to `fonts.googleapis.com` is
  blocked by the sandbox's network allowlist. This is a pre-existing
  environment constraint, not something introduced by this phase.
  Recommend running `npm run build` and hitting `/robots.txt`,
  `/sitemap.xml`, and a few key pages in a normal deploy environment
  before shipping.
- No Lighthouse or Search Console data was collected or claimed, per the
  prompt's explicit rule against fabricating either.

## Remaining work

Everything in `REMAINING_WORK.md`'s Tier 3 list is still open and
untouched by this phase (SMS alerts, OpenTelemetry instrumentation, k8s
infra manifests, Java SDK Maven verification) — none of it is SEO-related
so none of it was in scope here.
