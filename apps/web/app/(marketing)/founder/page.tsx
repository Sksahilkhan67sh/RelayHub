import type { Metadata } from "next";
import Image from "next/image";
import { Github, Linkedin, Mail, Code2, Rocket, Cloud, Brain, Layers, ListChecks } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Founder — RelayHub",
  description: "Meet the founder of RelayHub.",
  alternates: { canonical: "/founder" },
  openGraph: { title: "Founder — RelayHub", description: "Meet the founder of RelayHub.", url: "/founder" },
};

const INTERESTS = [
  { label: "Full-Stack Development", icon: Layers },
  { label: "SaaS", icon: Rocket },
  { label: "AI", icon: Brain },
  { label: "Cloud", icon: Cloud },
  { label: "System Design", icon: Code2 },
  { label: "DSA", icon: ListChecks },
];

const STACK = [
  "Python",
  "Django",
  "JavaScript",
  "React",
  "Next.js",
  "Node.js",
  "SQL",
  "PostgreSQL",
  "AWS",
];

const LINKS = [
  { label: "Email", href: "mailto:sahilkhan67sh@gmail.com", icon: Mail },
  { label: "LinkedIn", href: "https://www.linkedin.com/in/sahil--dev--py/", icon: Linkedin },
  { label: "GitHub", href: "https://github.com/Sksahilkhan67sh", icon: Github },
  { label: "LeetCode", href: "https://leetcode.com/u/sksahilkhan67sh/", icon: Code2 },
];

export default function FounderPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <div className="grid gap-10 sm:grid-cols-[220px_1fr] sm:items-start">
          <div className="mx-auto sm:mx-0">
            <div className="relative h-44 w-44 overflow-hidden rounded-full border border-graphite-100 shadow-card dark:border-graphite-800 sm:h-52 sm:w-52">
              <Image
                src="/images/sahil-khan.png"
                alt="Sahil Khan"
                fill
                sizes="220px"
                className="object-cover"
                priority
              />
            </div>
          </div>

          <div>
            <Eyebrow>Founder</Eyebrow>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
              Sahil Khan
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              B.Tech in Computer Science &amp; Technology (2026) and an aspiring full-stack developer passionate about
              building scalable, user-focused web applications. I enjoy solving complex problems, strengthening my DSA
              skills, and turning ideas into real-world products.
            </p>
            <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              I&apos;m also the founder of <span className="font-medium text-graphite-800 dark:text-graphite-200">AlignCraft</span>,
              where I focus on building innovative technology products and SaaS solutions &mdash; RelayHub is one of
              them.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              {LINKS.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  target={link.href.startsWith("http") ? "_blank" : undefined}
                  rel={link.href.startsWith("http") ? "noopener noreferrer" : undefined}
                  className="inline-flex items-center gap-1.5 rounded border border-graphite-200 px-3 py-1.5 text-[13px] font-medium text-graphite-700 transition-colors hover:border-signal-amber hover:text-signal-amber dark:border-graphite-700 dark:text-graphite-200"
                >
                  <link.icon className="h-3.5 w-3.5" />
                  {link.label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-16">
          <SectionHeading eyebrow="Stack" title="What I build with" />
          <div className="mt-8 flex flex-wrap gap-2.5">
            {STACK.map((tech) => (
              <span
                key={tech}
                className="rounded-full border border-graphite-200 bg-white px-3.5 py-1.5 text-[13px] font-medium text-graphite-700 dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-200"
              >
                {tech}
              </span>
            ))}
          </div>
        </Section>
      </div>

      <Section>
        <SectionHeading eyebrow="Interests" title="What I care about" />
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {INTERESTS.map((item) => (
            <div key={item.label} className="flex items-center gap-3">
              <item.icon className="h-4.5 w-4.5 shrink-0 text-signal-amber" />
              <span className="text-[13.5px] font-medium text-graphite-800 dark:text-graphite-200">{item.label}</span>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}
