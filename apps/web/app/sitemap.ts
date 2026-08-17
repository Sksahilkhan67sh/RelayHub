import type { MetadataRoute } from "next";
import type { BlogPostOut } from "@/lib/types";

const BASE_URL = "https://relayhub.dev";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATIC_ROUTES = [
  "",
  "/features",
  "/developers",
  "/developers/quickstart",
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

async function getPublishedBlogSlugs(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/v1/content/blog-posts`, { next: { revalidate: 3600 } });
    if (!res.ok) return [];
    const posts: BlogPostOut[] = await res.json();
    return posts.map((p) => p.slug);
  } catch {
    return []; // sitemap generation shouldn't fail the whole build/request if the API is briefly unreachable
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticEntries = STATIC_ROUTES.map((route) => {
    const changeFrequency: "weekly" | "monthly" = route === "" ? "weekly" : "monthly";
    return {
      url: `${BASE_URL}${route}`,
      lastModified: new Date(),
      changeFrequency,
      priority: route === "" ? 1 : 0.6,
    };
  });

  const slugs = await getPublishedBlogSlugs();
  const blogEntries = slugs.map((slug) => ({
    url: `${BASE_URL}/blog/${slug}`,
    lastModified: new Date(),
    changeFrequency: "monthly" as const,
    priority: 0.5,
  }));

  return [...staticEntries, ...blogEntries];
}
