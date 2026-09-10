"use client";

import type { ToolEvent } from "@/lib/types";
import { Label } from "@/components/ui/primitives";

/**
 * The agent's real work, as it happens.
 *
 * Every row is a tool the agent actually called — the backend writes one
 * tool_events row per invocation and streams it. Nothing here is simulated or
 * replayed, which is the point: it is evidence, not a loading animation.
 */

const TOOL_LABELS: Record<string, string> = {
  get_user_profile: "Reviewing what you've told me",
  update_user_profile: "Understanding your plans",
  search_cards: "Searching the catalogue",
  get_card_details: "Reading published fees",
  research_card: "Checking the provider's current terms",
  get_fx_rate: "Fetching today's reference rate",
  calculate_card_cost: "Costing it against your usage",
  compare_cards: "Ranking every eligible card",
  get_application_link: "Finding the application route",
  get_card_sources: "Collecting sources",
};

function Icon({ status }: { status: ToolEvent["status"] }) {
  if (status === "started") {
    return (
      <span
        aria-hidden
        className="mt-1 block size-3 shrink-0 animate-spin rounded-full border border-ink-600 border-t-ember-500"
      />
    );
  }
  if (status === "error") {
    return (
      <span aria-hidden className="mt-0.5 block size-3 shrink-0 text-center text-xs text-amber-400">
        ×
      </span>
    );
  }
  return (
    <span aria-hidden className="mt-0.5 block size-3 shrink-0 text-center text-xs text-jade-400">
      ✓
    </span>
  );
}

export function AgentActivity({ events }: { events: ToolEvent[] }) {
  if (events.length === 0) return null;

  return (
    <section
      aria-label="Agent activity"
      className="rounded-[--radius-card] border border-ink-800 bg-ink-900/60 p-4"
    >
      <Label>What the agent is doing</Label>
      <ol className="mt-3 space-y-2">
        {events.map((event) => (
          <li key={event.id} className="flex gap-2.5">
            <Icon status={event.status} />
            <div className="min-w-0 flex-1">
              <span className="text-sm text-mist-200">
                {TOOL_LABELS[event.tool_name] ?? event.tool_name.replace(/_/g, " ")}
              </span>
              {event.status !== "started" && event.duration_ms !== null && (
                <span className="tnum ml-2 font-mono text-[10px] text-mist-500">
                  {event.duration_ms}ms
                </span>
              )}
              {event.output_summary && (
                <p className="truncate text-xs text-mist-500">{event.output_summary}</p>
              )}
              {event.error_message && (
                <p className="text-xs text-amber-400">{event.error_message}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
