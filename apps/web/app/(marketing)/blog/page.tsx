import type { Metadata } from "next";
import { BlogClient } from "@/components/marketing/blog-client";

export const metadata: Metadata = {
  title: "Blog — RelayHub",
  description: "Notes on webhook reliability, retries, security, and how RelayHub is built.",
  alternates: { canonical: "/blog" },
  openGraph: { title: "Blog — RelayHub", description: "Notes on webhook reliability, retries, security, and engineering.", url: "/blog" },
};

export default function BlogPage() {
  return <BlogClient />;
}
