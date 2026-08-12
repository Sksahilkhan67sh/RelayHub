import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/card";
import { BLOG_POSTS, getPostBySlug } from "@/lib/blog-data";

export function generateStaticParams() {
  return BLOG_POSTS.map((p) => ({ slug: p.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const post = getPostBySlug(params.slug);
  if (!post) return {};
  return {
    title: `${post.title} — RelayHub Blog`,
    description: post.excerpt,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: { title: post.title, description: post.excerpt, url: `/blog/${post.slug}`, type: "article" },
  };
}

export default function BlogPostPage({ params }: { params: { slug: string } }) {
  const post = getPostBySlug(params.slug);
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
            {post.author.name[0]}
          </span>
          <div>
            <p className="text-xs font-medium text-graphite-800 dark:text-graphite-200">
              {post.author.name} <span className="font-normal text-graphite-400">· {post.author.role}</span>
            </p>
            <p className="text-[11px] text-graphite-500">
              {post.date} · {post.readMinutes} min read
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
