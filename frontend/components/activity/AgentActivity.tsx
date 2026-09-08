"use client";

import type { ToolEvent } from "@/lib/types";

/**
 * The agent's real work, as it happens.
 *
 * Every row here corresponds to a tool the agent actually called — the backend
 * writes one tool_events row per invocation and streams it. Nothing on this
 * panel is simulated, staged or replayed.
 */

const TOOL_LABELS: Record<string, string> = {
  get_user_profile: "Reviewing what you've told me",
  update_user_profile: "Understanding your plans",
  search_cards: "Searching the card catalogue",
  get_card_details: "Checking published fees",
  research_card: "Researching current provider information",
  get_fx_rate: "Checking today's exchange rate",
  calculate_card_cost: "Calculating your expected costs",
  compare_cards: "Comparing cards for your usage",
  get_application_link: "Finding the application route",
  get_card_sources: "Collecting sources",
};

function label(tool: string): string {
  return TOOL_LABELS[tool] ?? tool.replace(/_/g, " ");
}

function Icon({ status }: { status: ToolEvent["status"] }) {
  if (status === "started") {
    return (
      <span
        aria-hidden
        className="mt-[3px] block size-3.5 shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600 dark:border-slate-600 dark:border-t-slate-300"
      />
    );
  }
  if (status === "error") {
    return (
      <span aria-hidden className="mt-[3px] block size-3.5 shrink-0 text-rose-600 dark:text-rose-400">
        ✕
      </span>
    );
  }
  return (
    <span aria-hidden className="mt-[3px] block size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400">
      ✓
    </span>
  );
}

export function AgentActivity({ events }: { events: ToolEvent[] }) {
  if (events.length === 0) return null;

  return (
    <section
      aria-label="Agent activity"
      className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-sm dark:border-slate-800 dark:bg-slate-900/40"
    >
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        What the agent is doing
      </h2>
      <ol className="space-y-1.5">
        {events.map((event) => (
          <li key={event.id} className="flex gap-2">
            <Icon status={event.status} />
            <div className="min-w-0">
              <span className="text-slate-800 dark:text-slate-200">{label(event.tool_name)}</span>
              {event.status !== "started" && event.duration_ms !== null && (
                <span className="ml-2 text-xs text-slate-400 tabular-nums dark:text-slate-500">
                  {event.duration_ms}ms
                </span>
              )}
              {event.output_summary && (
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                  {event.output_summary}
                </p>
              )}
              {event.error_message && (
                <p className="text-xs text-rose-600 dark:text-rose-400">{event.error_message}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
