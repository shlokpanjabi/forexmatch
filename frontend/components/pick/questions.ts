/**
 * The wizard's questions.
 *
 * Only things that change the ranking are asked — six screens, roughly a
 * minute. Everything here maps onto the UserProfile the engine already
 * consumes, so the wizard and the agent produce identical input.
 */

export interface Destination {
  id: string;
  country: string;
  currency: string;
  symbol: string;
}

export const DESTINATIONS: Destination[] = [
  { id: "uk", country: "United Kingdom", currency: "GBP", symbol: "£" },
  { id: "us", country: "United States", currency: "USD", symbol: "$" },
  { id: "ca", country: "Canada", currency: "CAD", symbol: "C$" },
  { id: "au", country: "Australia", currency: "AUD", symbol: "A$" },
  { id: "de", country: "Germany", currency: "EUR", symbol: "€" },
  { id: "ie", country: "Ireland", currency: "EUR", symbol: "€" },
  { id: "nl", country: "Netherlands", currency: "EUR", symbol: "€" },
  { id: "fr", country: "France", currency: "EUR", symbol: "€" },
  { id: "sg", country: "Singapore", currency: "SGD", symbol: "S$" },
  { id: "ae", country: "United Arab Emirates", currency: "AED", symbol: "AED " },
  { id: "nz", country: "New Zealand", currency: "NZD", symbol: "NZ$" },
  { id: "ch", country: "Switzerland", currency: "CHF", symbol: "CHF " },
];

export interface Choice {
  value: string;
  label: string;
  hint?: string;
}

export const DURATIONS: Choice[] = [
  { value: "6", label: "A semester", hint: "About 6 months" },
  { value: "12", label: "One year", hint: "A one-year master's" },
  { value: "24", label: "Two years", hint: "Most master's programmes" },
  { value: "36", label: "Three years or more", hint: "Undergraduate or PhD" },
];

/** Bands in the destination currency. "Not sure" is a first-class answer. */
export const SPEND_BANDS: Array<Choice & { min: number | null; max: number | null }> = [
  { value: "low", label: "Under 600", min: 300, max: 600, hint: "Halls, cooking at home" },
  { value: "mid", label: "600 – 1,000", min: 600, max: 1000 },
  { value: "high", label: "1,000 – 1,500", min: 1000, max: 1500, hint: "Typical for a city" },
  { value: "higher", label: "1,500 – 2,500", min: 1500, max: 2500 },
  { value: "top", label: "Over 2,500", min: 2500, max: 3500 },
  {
    value: "unsure",
    label: "I'm not sure yet",
    min: 800,
    max: 1500,
    hint: "We'll use a range and say so",
  },
];

export const ATM_USAGE: Choice[] = [
  { value: "none", label: "Never", hint: "Card everywhere" },
  { value: "low", label: "Rarely", hint: "Maybe once a month" },
  { value: "medium", label: "Sometimes", hint: "About once a week" },
  { value: "high", label: "Often", hint: "Several times a week" },
];

export const CURRENCY_SPREAD: Choice[] = [
  { value: "single", label: "Mostly one country", hint: "I'll spend in one currency" },
  { value: "multiple", label: "I'll travel around", hint: "Several currencies" },
];

/** Maps to the six scoring weights. One primary priority, normalised server-side. */
export const PRIORITIES: Array<Choice & { weights: Record<string, number> }> = [
  {
    value: "cost",
    label: "Keeping fees low",
    hint: "The cheapest card for my usage",
    weights: { cost: 0.7, atm: 0.1, currency_support: 0.1, convenience: 0.05, rewards: 0, security: 0.05 },
  },
  {
    value: "atm",
    label: "Getting cash easily",
    hint: "Cheap, reliable ATM access",
    weights: { cost: 0.25, atm: 0.5, currency_support: 0.1, convenience: 0.1, rewards: 0, security: 0.05 },
  },
  {
    value: "rewards",
    label: "Rewards and perks",
    hint: "Cashback, lounges, insurance",
    weights: { cost: 0.15, atm: 0.05, currency_support: 0.1, convenience: 0.1, rewards: 0.55, security: 0.05 },
  },
  {
    value: "convenience",
    label: "Being easy to run",
    hint: "Apply and reload online",
    weights: { cost: 0.25, atm: 0.05, currency_support: 0.1, convenience: 0.5, rewards: 0.05, security: 0.05 },
  },
  {
    value: "security",
    label: "Safety if it goes wrong",
    hint: "Fraud cover, fast replacement",
    weights: { cost: 0.25, atm: 0.05, currency_support: 0.1, convenience: 0.1, rewards: 0, security: 0.5 },
  },
];

export interface Answers {
  destination?: Destination;
  duration?: string;
  spend?: (typeof SPEND_BANDS)[number];
  atm?: string;
  spread?: string;
  priority?: (typeof PRIORITIES)[number];
}

/** Turn the answers into the profile the recommendation endpoint expects. */
export function toProfile(answers: Answers) {
  const spend = answers.spend;
  const currency = answers.destination?.currency ?? "USD";
  return {
    destination_country: answers.destination?.country ?? null,
    destination_currencies: answers.destination ? [answers.destination.currency] : [],
    trip_type: "study",
    trip_duration_months: answers.duration ? Number(answers.duration) : null,
    student_status: true,
    monthly_spend: {
      min_amount: spend?.min != null ? String(spend.min) : null,
      max_amount: spend?.max != null ? String(spend.max) : null,
      currency,
      // A band is an estimate, and a band the user could not choose doubly so.
      confidence: spend?.value === "unsure" ? "assumed" : "estimated",
    },
    atm_usage: answers.atm ?? "unknown",
    needs_multiple_currencies: answers.spread === "multiple",
    priorities: answers.priority?.weights ?? undefined,
    priorities_customised: Boolean(answers.priority),
  };
}

export const TOTAL_STEPS = 6;
