"use client";

import type { Profile } from "@/lib/types";
import { Label } from "@/components/ui/primitives";

/**
 * What the agent has understood so far.
 *
 * Ranges stay ranges: an estimate is never redisplayed as a precise figure.
 */
export function ProfileSummary({ profile }: { profile: Profile }) {
  const spend = profile.monthly_spend;
  const facts: Array<[string, string]> = [];

  if (profile.destination_country) facts.push(["Destination", profile.destination_country]);
  if (profile.destination_currencies.length > 0)
    facts.push(["Spending in", profile.destination_currencies.join(", ")]);
  if (profile.trip_duration_months) facts.push(["Staying", `${profile.trip_duration_months} months`]);

  if (spend.min_amount || spend.max_amount) {
    const currency = spend.currency ?? "";
    const min = spend.min_amount ? Math.round(Number(spend.min_amount)).toLocaleString() : null;
    const max = spend.max_amount ? Math.round(Number(spend.max_amount)).toLocaleString() : null;
    const range = min && max && min !== max ? `${min}–${max}` : (min ?? max);
    const qualifier = spend.confidence === "stated" ? "" : " (est.)";
    facts.push(["Monthly spend", `${currency} ${range}${qualifier}`.trim()]);
  }

  if (profile.atm_withdrawals_per_month !== null)
    facts.push(["Cash", `${profile.atm_withdrawals_per_month}× a month`]);
  else if (profile.atm_usage !== "unknown") facts.push(["Cash use", profile.atm_usage]);

  if (profile.priorities_customised) {
    const top = Object.entries(profile.priorities).sort((a, b) => b[1] - a[1])[0];
    if (top) facts.push(["Priority", top[0].replace(/_/g, " ")]);
  }

  if (facts.length === 0) return null;

  return (
    <section
      aria-label="What we understood"
      className="rounded-[--radius-card] border border-ink-800 bg-ink-900 p-4"
    >
      <Label>What we understood</Label>
      <dl className="mt-3 grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="font-mono text-[10px] uppercase tracking-wider text-mist-500">{label}</dt>
            <dd className="mt-0.5 text-sm text-mist-100">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
