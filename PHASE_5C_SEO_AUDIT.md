# PHASE 5C SEO AUDIT

## Baseline finding

The marketing site (`apps/web/app/(marketing)`) already has a **substantial**
SEO foundation from prior phases — this is not a from-scratch SEO build:

- `app/robots.ts` — real robots.txt, correctly allows `/` and disallows every
  authenticated route (`/dashboard`, `/settings`, `/admin`, `/endpoints`,
  `/events`, `/deliveries`, `/dlq`, `/retry-queue`, `/analytics`, `/alerts`,
  `/api-keys`, `/billing`, `/usage`, `/logs`).
- `app/sitemap.ts` — real, dynamic sitemap: 26 static marketing routes +
  live blog slugs fetched from `/v1/content/blog-posts`. No dashboard/admin
  URLs, no fabricated entries.
- `app/manifest.ts` — real web manifest with real icons.
- Root `layout.tsx` — sets `metadataBase`, a title template, and a base
  `twitter.card`.
- **26/26 marketing `page.tsx` files already export `metadata`** with a
  unique title + description. `blog/[slug]/page.tsx` uses `generateMetadata`
  against real post data (no static/fake slugs).
- 26/26 pages set `alternates.canonical`.

So Phase 5C's real, evidence-based scope is the **gaps** in that existing
system, not a rebuild.

## Public URL inventory (summary — full detail lives in sitemap.ts / robots.ts)

| Category | Routes | Status |
|---|---|---|
| Public indexable (static) | `/`, `/features`, `/pricing`, `/about`, `/founder`, `/careers`, `/contact`, `/changelog`, `/status`, `/docs`, `/developers` + 9 sub-pages, `/login`, `/register` | In sitemap, has metadata + canonical |
| Public indexable (dynamic) | `/blog`, `/blog/[slug]` | In sitemap (slugs from live API), `generateMetadata` |
| Public non-indexable (legal, low-priority) | `/privacy`, `/terms`, `/cookies` | In sitemap, has metadata, **missing `openGraph`** |
| Authenticated (must stay out of index) | `/dashboard`, `/settings/*`, `/admin/*`, `/endpoints/*`, `/events`, `/deliveries/*`, `/dlq`, `/retry-queue`, `/analytics`, `/alerts`, `/api-keys`, `/billing`, `/usage`, `/logs`, `/intelligence/*` | In `robots.ts` disallow list; **no HTTP-level `X-Robots-Tag`/`noindex` backstop** — relies on robots.txt alone, which doesn't stop indexing of a URL that gets linked to externally |
| Auth flow (public, thin) | `/forgot-password`, `/reset-password`, `/accept-invitation`, `/invitation-*` | Not in sitemap (correct — no evergreen search value); not disallowed either, which is fine |
| Utility | `/robots.txt`, `/sitemap.xml`, `/manifest.webmanifest` | Working |

## Findings, by SEO area

| Area | Status | Action |
|---|---|---|
| Titles | ✅ PASS — unique per page, product-accurate | none |
| Meta descriptions | ✅ PASS — unique, no stuffing | none |
| Canonical URLs | ✅ PASS — 26/26 pages, correct `https://relayhub.dev` domain | none |
| Robots.txt | ✅ PASS | none |
| Sitemap | ✅ PASS | none |
| **Open Graph** | ⚠️ PARTIAL — 23/26 pages set it; `terms`, `cookies`, `privacy` don't | Add |
| **OG/Twitter images** | ❌ MISSING — no page anywhere sets `openGraph.images` or `twitter.images`; no image asset exists for this in `public/` | Add a real generated image (`next/og`), not a placeholder |
| **JSON-LD structured data** | ⚠️ PARTIAL — only the homepage has any (`SoftwareApplication`), and its `offers` block claims a flat `"price": "0"`, which misrepresents the real Starter ($29) / Pro ($99) tiers | Fix to reflect real pricing (`AggregateOffer`); add `Organization`/`WebSite` site-wide; add `Article` to blog posts |
| Blog SEO | ⚠️ PARTIAL — title/description/canonical/OG all real and dynamic; no `Article` JSON-LD, no author/date structured data | Add `Article` JSON-LD from real post fields |
| Semantic HTML / H1 | ✅ PASS (spot-checked homepage, pricing, blog, features — single real `<h1>`, `<header>`/`<main>`/`<footer>` via shared layout) | none needed |
| **Authenticated-route indexability** | ⚠️ Robots.txt disallow only — no `X-Robots-Tag` header backstop, and `(dashboard)/layout.tsx` is a client component so it can't export `metadata.robots` | Add `middleware.ts` sending `X-Robots-Tag: noindex, nofollow` for the same route list already in `robots.ts` |
| Redirects | N/A — no URL changes made this phase | none |
| Backend impact | None required — all gaps are frontend metadata/markup | none |

## Exact Phase 5C scope (evidence-based, from the above)

1. Add `openGraph` to the 3 legal pages missing it.
2. Add a real, dynamically-generated default OG/Twitter image (`next/og`),
   wired into root metadata so every page inherits it unless overridden.
3. Add site-wide `Organization` + `WebSite` JSON-LD (root layout).
4. Fix the homepage's `SoftwareApplication` JSON-LD `offers` to reflect the
   real Free/Starter/Pro pricing instead of a flat, misleading `$0`.
5. Add `Article` JSON-LD to blog posts, from real post data only.
6. Add an `X-Robots-Tag: noindex, nofollow` middleware for authenticated
   routes, as a backstop to the existing robots.txt disallow list.

Not in scope (no evidence of a real gap, or explicitly excluded by the
prompt): sitemap/robots rebuild, URL restructuring, redirects, backend
changes, third-party SEO libraries, mass content generation, fabricated
FAQ/review/rating schema, Lighthouse/Search Console claims.
