import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/card";
import type { BlogPostOut } from "@/lib/types";

// Fetched per-request rather than statically generated at build time: posts are
// now created/edited/published by admins through the API at any time, so the set
// of valid slugs isn't knowable at build time.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getPostBySlug(slug: string): Promise<BlogPostOut | null> {
  const res = await fetch(`${API_BASE_URL}/v1/content/blog-posts/${encodeURIComponent(slug)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to load post: ${res.status}`);
  return res.json();
}

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const post = await getPostBySlug(params.slug).catch(() => null);
  if (!post) return {};
  return {
    title: `${post.title} — RelayHub Blog`,
    description: post.excerpt,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: { title: post.title, description: post.excerpt, url: `/blog/${post.slug}`, type: "article" },
  };
}

export default async function BlogPostPage({ params }: { params: { slug: string } }) {
  const post = await getPostBySlug(params.slug);
  if (!post) notFound();

  return (
    <article className="mx-auto max-w-2xl px-5 py-16 sm:py-20">
      <Link href="/blog" className="flex w-fit items-center gap-1.5 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to blog
      </Link>

      <div className="mt-6">
        <Badge tone="neutral">{post.category}</Badge>
        <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-graphite-950 sm:text-4xl dark:text-graphite-50">{post.title}</h1>
        <div className="mt-5 flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-signal-amber text-xs font-semibold text-white">
            {post.author_name[0]}
          </span>
          <div>
            <p className="text-xs font-medium text-graphite-800 dark:text-graphite-200">
              {post.author_name} <span className="font-normal text-graphite-400">· {post.author_role}</span>
            </p>
            <p className="text-[11px] text-graphite-500">
              {post.published_at ?? new Date(post.created_at).toLocaleDateString()} · {post.read_minutes} min read
            </p>
          </div>
        </div>
      </div>

      <div className="prose-content mt-10 flex flex-col gap-5">
        {post.body.map((para, i) => (
          <p key={i} className="text-[14.5px] leading-relaxed text-graphite-700 dark:text-graphite-300">
            {para}
          </p>
        ))}
      </div>

      <div className="mt-16 border-t border-graphite-100 pt-6 dark:border-graphite-800">
        <Link href="/blog" className="text-xs font-medium text-signal-amber hover:underline">
          ← All posts
        </Link>
      </div>
    </article>
  );
}
