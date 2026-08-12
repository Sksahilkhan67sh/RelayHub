import type { Metadata } from "next";
import { DocsClient } from "@/components/marketing/docs-client";

export const metadata: Metadata = {
  title: "Documentation — RelayHub",
  description: "Everything you need to send, receive, and debug webhooks with RelayHub: authentication, API keys, events, endpoints, retries, replay, and more.",
  alternates: { canonical: "/docs" },
  openGraph: { title: "Documentation — RelayHub", description: "Guides for authentication, events, endpoints, retries, replay, and the dead-letter queue.", url: "/docs" },
};

export default function DocsPage() {
  return <DocsClient />;
}
