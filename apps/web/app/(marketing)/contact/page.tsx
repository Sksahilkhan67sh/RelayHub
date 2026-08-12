import type { Metadata } from "next";
import { ContactClient } from "@/components/marketing/contact-client";

export const metadata: Metadata = {
  title: "Contact — RelayHub",
  description: "Reach RelayHub support, sales, or the product team -- or report a bug.",
  alternates: { canonical: "/contact" },
  openGraph: { title: "Contact — RelayHub", description: "Get in touch with support, sales, or the product team.", url: "/contact" },
};

export default function ContactPage() {
  return <ContactClient />;
}
