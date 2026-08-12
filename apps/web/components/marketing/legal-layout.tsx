export function LegalLayout({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl px-5 py-16 sm:py-20">
      <h1 className="text-3xl font-semibold tracking-tight text-graphite-950 sm:text-4xl dark:text-graphite-50">{title}</h1>
      <p className="mt-2 text-xs text-graphite-500">Last updated {updated}</p>
      <div className="prose-legal mt-10 flex flex-col gap-7 text-[13.5px] leading-relaxed text-graphite-700 dark:text-graphite-300">
        {children}
      </div>
    </div>
  );
}

export function LegalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2.5">
      <h2 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">{title}</h2>
      {children}
    </section>
  );
}
