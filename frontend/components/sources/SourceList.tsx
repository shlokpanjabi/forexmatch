"use client";

import type { Source } from "@/lib/types";

const TYPE_LABELS: Record<string, string> = {
  official_product_page: "Official product page",
  official_fee_schedule: "Official fee schedule",
  official_terms: "Official terms",
  official_faq: "Official FAQ",
  secondary_source: "Secondary source",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function SourceList({ sources, title = "Sources" }: { sources: Source[]; title?: string }) {
  if (sources.length === 0) return null;

  return (
    <div>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </h3>
      <ul className="space-y-1.5">
        {sources.map((source) => (
          <li key={source.url} className="text-sm">
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-700 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600 dark:text-slate-300 dark:decoration-slate-600"
            >
              {source.title ?? source.domain}
            </a>
            <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
              {TYPE_LABELS[source.source_type] ?? source.source_type}
              {" · "}
              Verified {formatDate(source.last_verified_at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
