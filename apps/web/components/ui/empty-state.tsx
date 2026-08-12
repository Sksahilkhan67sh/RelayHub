import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-graphite-100 dark:bg-graphite-800">
        <Icon className="h-5 w-5 text-graphite-400" />
      </div>
      <div>
        <h3 className="text-sm font-medium text-graphite-950 dark:text-graphite-50">{title}</h3>
        <p className="mt-1 max-w-xs text-xs text-graphite-600 dark:text-graphite-400">{description}</p>
      </div>
      {actionLabel && onAction && (
        <Button size="sm" onClick={onAction} className="mt-1">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
