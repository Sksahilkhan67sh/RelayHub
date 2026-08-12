import { Construction } from "lucide-react";

export function ComingSoon({ title }: { title: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 py-24 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-graphite-100 dark:bg-graphite-800">
        <Construction className="h-5 w-5 text-graphite-400" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{title}</h2>
        <p className="mt-1 max-w-xs text-xs text-graphite-600 dark:text-graphite-400">
          This page isn&apos;t built yet in the current session. The backend API it needs already exists and is fully
          tested -- this is a frontend build-order gap, not a missing feature.
        </p>
      </div>
    </div>
  );
}
