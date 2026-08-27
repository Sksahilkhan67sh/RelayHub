import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Backstop for the authenticated route list in app/robots.ts. robots.txt only
// stops a *compliant* crawler from choosing to crawl these paths -- it does
// nothing once a URL is already discovered (e.g. linked externally, shared in
// a support ticket) and a crawler indexes it anyway. Sending X-Robots-Tag at
// the HTTP layer blocks indexing of the response itself, regardless of how a
// crawler found the URL. Kept in sync with app/robots.ts's disallow list.
const NOINDEX_PREFIXES = [
  "/dashboard",
  "/settings",
  "/admin",
  "/endpoints",
  "/events",
  "/deliveries",
  "/dlq",
  "/retry-queue",
  "/analytics",
  "/alerts",
  "/api-keys",
  "/billing",
  "/usage",
  "/logs",
  "/intelligence",
];

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const { pathname } = request.nextUrl;

  if (NOINDEX_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }

  return response;
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/settings/:path*",
    "/admin/:path*",
    "/endpoints/:path*",
    "/events/:path*",
    "/deliveries/:path*",
    "/dlq/:path*",
    "/retry-queue/:path*",
    "/analytics/:path*",
    "/alerts/:path*",
    "/api-keys/:path*",
    "/billing/:path*",
    "/usage/:path*",
    "/logs/:path*",
    "/intelligence/:path*",
  ],
};
