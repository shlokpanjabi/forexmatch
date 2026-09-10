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
  /**
   * Monthly spend band edges in the local currency, as [min, max]. The last
   * band is open-ended.
   *
   * These are rough guides so the options land near what a student in that
   * country would actually recognise — £600 and AED 600 are not the same
   * question. They are not a claim about cost of living: the user picks the
   * band that matches them, so the resulting figure is their statement, and it
   * is recorded as an estimate either way.
   */
  bands: Array<[number, number]>;
}

export const DESTINATIONS: Destination[] = [
  { id: "uk", country: "United Kingdom", currency: "GBP", symbol: "£",
    bands: [[350, 600], [600, 900], [900, 1300], [1300, 1800], [1800, 2600]] },
  { id: "us", country: "United States", currency: "USD", symbol: "$",
    bands: [[500, 800], [800, 1200], [1200, 1800], [1800, 2500], [2500, 3500]] },
  { id: "ca", country: "Canada", currency: "CAD", symbol: "C$",
    bands: [[700, 1000], [1000, 1500], [1500, 2000], [2000, 2800], [2800, 3800]] },
  { id: "au", country: "Australia", currency: "AUD", symbol: "A$",
    bands: [[800, 1200], [1200, 1800], [1800, 2400], [2400, 3200], [3200, 4400]] },
  { id: "de", country: "Germany", currency: "EUR", symbol: "€",
    bands: [[400, 700], [700, 1000], [1000, 1400], [1400, 1900], [1900, 2600]] },
  { id: "ie", country: "Ireland", currency: "EUR", symbol: "€",
    bands: [[600, 900], [900, 1300], [1300, 1800], [1800, 2400], [2400, 3200]] },
  { id: "nl", country: "Netherlands", currency: "EUR", symbol: "€",
    bands: [[600, 900], [900, 1250], [1250, 1700], [1700, 2300], [2300, 3100]] },
  { id: "fr", country: "France", currency: "EUR", symbol: "€",
    bands: [[500, 800], [800, 1150], [1150, 1600], [1600, 2200], [2200, 3000]] },
  { id: "sg", country: "Singapore", currency: "SGD", symbol: "S$",
    bands: [[700, 1000], [1000, 1500], [1500, 2100], [2100, 2900], [2900, 4000]] },
  { id: "ae", country: "United Arab Emirates", currency: "AED", symbol: "AED ",
    bands: [[1800, 2800], [2800, 4200], [4200, 6000], [6000, 8500], [8500, 12000]] },
  { id: "nz", country: "New Zealand", currency: "NZD", symbol: "NZ$",
    bands: [[800, 1200], [1200, 1800], [1800, 2400], [2400, 3200], [3200, 4400]] },
  { id: "ch", country: "Switzerland", currency: "CHF", symbol: "CHF ",
    bands: [[1100, 1600], [1600, 2200], [2200, 3000], [3000, 4000], [4000, 5500]] },
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

export interface SpendBand extends Choice {
  min: number;
  max: number;
}

const BAND_HINTS = [
  "Halls, cooking at home",
  "Modest, shared housing",
  "Typical for a city",
  "Comfortable, eating out",
  "Central, few compromises",
];

function money(symbol: string, amount: number): string {
  return `${symbol}${amount.toLocaleString("en-GB")}`;
}

/**
 * Spend options for a destination.
 *
 * "I'm not sure" is a first-class answer, not a cop-out: it spans the two
 * middle bands and is recorded with lower confidence, so the estimate the
 * engine works from is honest about how it was arrived at.
 */
export function spendBandsFor(destination: Destination | undefined): SpendBand[] {
  const bands = destination?.bands ?? [
    [500, 800],
    [800, 1200],
    [1200, 1800],
    [1800, 2500],
    [2500, 3500],
  ];
  const symbol = destination?.symbol ?? "";

  const options: SpendBand[] = bands.map(([min, max], i) => ({
    value: `band-${i}`,
    label:
      i === 0
        ? `Under ${money(symbol, max)}`
        : i === bands.length - 1
          ? `Over ${money(symbol, min)}`
          : `${money(symbol, min)} – ${money(symbol, max)}`,
    hint: BAND_HINTS[i],
    min,
    max,
  }));

  const lower = bands[1] ?? bands[0];
  const upper = bands[2] ?? bands[bands.length - 1];
  options.push({
    value: "unsure",
    label: "I'm not sure yet",
    hint: `We'll assume ${money(symbol, lower[0])}–${money(symbol, upper[1])} and say so`,
    min: lower[0],
    max: upper[1],
  });

  return options;
}

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
  spend?: SpendBand;
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
