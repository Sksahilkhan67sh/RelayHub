import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/dashboard", "/settings", "/admin", "/endpoints", "/events", "/deliveries", "/dlq", "/retry-queue", "/analytics", "/alerts", "/api-keys", "/billing", "/usage", "/logs"],
      },
    ],
    sitemap: "https://relayhub.dev/sitemap.xml",
  };
}
