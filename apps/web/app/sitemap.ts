import type { MetadataRoute } from "next";
import { BLOG_POSTS } from "@/lib/blog-data";

const BASE_URL = "https://relayhub.dev";

const STATIC_ROUTES = [
  "",
  "/features",
  "/pricing",
  "/docs",
  "/about",
  "/founder",
  "/careers",
  "/contact",
  "/changelog",
  "/blog",
  "/privacy",
  "/terms",
  "/cookies",
  "/status",
  "/login",
  "/register",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const staticEntries = STATIC_ROUTES.map((route) => {
    const changeFrequency: "weekly" | "monthly" = route === "" ? "weekly" : "monthly";
    return {
      url: `${BASE_URL}${route}`,
      lastModified: new Date(),
      changeFrequency,
      priority: route === "" ? 1 : 0.6,
    };
  });

  const blogEntries = BLOG_POSTS.map((post) => ({
    url: `${BASE_URL}/blog/${post.slug}`,
    lastModified: new Date(),
    changeFrequency: "monthly" as const,
    priority: 0.5,
  }));

  return [...staticEntries, ...blogEntries];
}
