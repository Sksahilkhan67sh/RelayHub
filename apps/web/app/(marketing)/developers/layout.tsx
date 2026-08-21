import { DocsSearch } from "@/components/search/docs-search";

export default function DevelopersLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div className="sticky top-16 z-30 border-b border-graphite-100 bg-white/90 backdrop-blur dark:border-graphite-800 dark:bg-graphite-950/90">
        <div className="mx-auto flex max-w-6xl items-center justify-end px-5 py-2.5">
          <DocsSearch />
        </div>
      </div>
      {children}
    </div>
  );
}
