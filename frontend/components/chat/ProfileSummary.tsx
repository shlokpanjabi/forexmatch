"use client";

import type { Profile } from "@/lib/types";

/**
 * What the agent has understood so far.
 *
 * Ranges are shown as ranges. BUILD.md section 9: an estimate must not be
 * redisplayed as a precise figure.
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
    const qualifier = spend.confidence === "stated" ? "" : " (estimated)";
    facts.push(["Monthly spend", `${currency} ${range}${qualifier}`.trim()]);
  }

  if (profile.atm_withdrawals_per_month !== null)
    facts.push(["Cash withdrawals", `${profile.atm_withdrawals_per_month} a month`]);
  else if (profile.atm_usage !== "unknown") facts.push(["Cash use", profile.atm_usage]);

  if (profile.priorities_customised) {
    const top = Object.entries(profile.priorities).sort((a, b) => b[1] - a[1])[0];
    if (top) facts.push(["Priority", top[0].replace(/_/g, " ")]);
  }

  if (facts.length === 0) return null;

  return (
    <section
      aria-label="What we understood"
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        What we understood
      </h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-3">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
            <dd className="text-slate-800 dark:text-slate-200">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
