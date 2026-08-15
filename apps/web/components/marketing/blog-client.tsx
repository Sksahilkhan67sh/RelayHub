"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { Search, Mail, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api-client";
import type { BlogPostOut } from "@/lib/types";

export function BlogClient() {
  const [posts, setPosts] = useState<BlogPostOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("All");
  const [email, setEmail] = useState("");
  const [newsletterNote, setNewsletterNote] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<BlogPostOut[]>("/v1/content/blog-posts")
      .then(setPosts)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load posts"));
  }, []);

  const categories = useMemo(() => {
    const set = new Set((posts ?? []).map((p) => p.category));
    return ["All", ...Array.from(set)];
  }, [posts]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (posts ?? []).filter(
      (p) =>
        (category === "All" || p.category === category) &&
        (!q || p.title.toLowerCase().includes(q) || p.excerpt.toLowerCase().includes(q))
    );
  }, [posts, query, category]);

  function handleNewsletterSubmit(e: FormEvent) {
    e.preventDefault();
    setNewsletterNote("Newsletter signup isn't wired up yet -- follow the Changelog for updates in the meantime.");
    setEmail("");
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-16 sm:py-20">
      <div className="max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-wider text-signal-amber">Blog</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Notes on reliability and engineering</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          How we build RelayHub, and what we&apos;ve learned about webhook delivery along the way.
        </p>
      </div>

      <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-graphite-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search posts"
            aria-label="Search blog posts"
            className="h-9 w-full rounded border border-graphite-200 bg-white pl-8 pr-2 text-xs dark:border-graphite-700 dark:bg-graphite-900"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                category === c
                  ? "bg-graphite-950 text-white dark:bg-graphite-50 dark:text-graphite-950"
                  : "border border-graphite-200 text-graphite-600 dark:border-graphite-700 dark:text-graphite-400"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {posts === null && !error ? (
        <div className="mt-16 flex justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-graphite-400" />
        </div>
      ) : error ? (
        <p className="mt-16 text-center text-sm text-signal-red">{error}</p>
      ) : (
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="flex flex-col gap-4 rounded-md border border-graphite-100 p-5 transition-colors hover:border-graphite-200 dark:border-graphite-800 dark:hover:border-graphite-700"
            >
              <Badge tone="neutral">{post.category}</Badge>
              <div>
                <h2 className="text-sm font-semibold leading-snug text-graphite-950 dark:text-graphite-50">{post.title}</h2>
                <p className="mt-2 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{post.excerpt}</p>
              </div>
              <div className="mt-auto flex items-center justify-between border-t border-graphite-100 pt-3 dark:border-graphite-800">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-signal-amber text-[10px] font-semibold text-white">
                    {post.author_name[0]}
                  </span>
                  <div>
                    <p className="text-[11px] font-medium text-graphite-800 dark:text-graphite-200">{post.author_name}</p>
                    <p className="text-[10px] text-graphite-500">{post.published_at ?? new Date(post.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <span className="text-[11px] text-graphite-400">{post.read_minutes} min</span>
              </div>
            </Link>
          ))}
          {filtered.length === 0 && <p className="col-span-full py-12 text-center text-sm text-graphite-500">No posts match that search.</p>}
        </div>
      )}

      <div className="mt-20 flex flex-col items-center gap-4 rounded-md border border-graphite-100 bg-graphite-50 p-8 text-center dark:border-graphite-800 dark:bg-graphite-900/40">
        <Mail className="h-5 w-5 text-signal-amber" />
        <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">Get new posts by email</h2>
        <p className="max-w-sm text-xs text-graphite-500">No spam, just new posts as we publish them.</p>
        <form onSubmit={handleNewsletterSubmit} className="flex w-full max-w-sm gap-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            aria-label="Email address"
            className="h-9 flex-1 rounded border border-graphite-200 bg-white px-3 text-xs dark:border-graphite-700 dark:bg-graphite-900"
          />
          <Button type="submit" size="sm">
            Subscribe
          </Button>
        </form>
        {newsletterNote && <p className="text-xs text-graphite-500">{newsletterNote}</p>}
      </div>
    </div>
  );
}
