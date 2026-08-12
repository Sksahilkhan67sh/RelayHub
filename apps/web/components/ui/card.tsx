import { cn } from "@/lib/cn";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-md border border-graphite-100 bg-white shadow-card dark:border-graphite-800 dark:bg-graphite-900",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("border-b border-graphite-100 px-4 py-3 dark:border-graphite-800", className)}>{children}</div>;
}

export function CardBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("p-4", className)}>{children}</div>;
}

type BadgeTone = "neutral" | "amber" | "green" | "red";

const BADGE_TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-graphite-100 text-graphite-700 dark:bg-graphite-800 dark:text-graphite-200",
  amber: "bg-signal-amber-soft text-[#8A5D1F]",
  green: "bg-signal-green-soft text-[#146245]",
  red: "bg-signal-red-soft text-[#8F311E]",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-sm px-1.5 py-0.5 text-xs font-medium", BADGE_TONE_CLASSES[tone])}>
      {children}
    </span>
  );
}
