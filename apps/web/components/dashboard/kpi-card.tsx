import { Card, CardBody } from "@/components/ui/card";
import { cn } from "@/lib/cn";

export function KpiCard({
  label,
  value,
  tone,
  suffix,
}: {
  label: string;
  value: string | number;
  tone?: "amber" | "green" | "red";
  suffix?: string;
}) {
  const toneClass =
    tone === "green" ? "text-signal-green" : tone === "red" ? "text-signal-red" : tone === "amber" ? "text-signal-amber" : "text-graphite-950 dark:text-graphite-50";

  return (
    <Card>
      <CardBody className="flex flex-col gap-1">
        <span className="text-xs text-graphite-600 dark:text-graphite-400">{label}</span>
        <span className={cn("tabular text-xl font-semibold", toneClass)}>
          {value}
          {suffix && <span className="ml-0.5 text-sm font-normal text-graphite-500">{suffix}</span>}
        </span>
      </CardBody>
    </Card>
  );
}
