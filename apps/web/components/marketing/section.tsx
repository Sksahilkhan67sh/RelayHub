import { cn } from "@/lib/cn";

export function Section({ className, children, id }: { className?: string; children: React.ReactNode; id?: string }) {
  return (
    <section id={id} className={cn("mx-auto max-w-6xl px-5 py-20 sm:py-24", className)}>
      {children}
    </section>
  );
}

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-signal-amber">
      <span className="h-1 w-1 rounded-full bg-signal-amber" />
      {children}
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "left",
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "left" | "center";
}) {
  return (
    <div className={cn("flex max-w-2xl flex-col gap-3", align === "center" && "mx-auto items-center text-center")}>
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="text-3xl font-semibold tracking-tight text-graphite-950 sm:text-4xl dark:text-graphite-50">{title}</h2>
      {description && <p className="text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">{description}</p>}
    </div>
  );
}
