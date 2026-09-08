import Link from "next/link";

export const metadata = { title: "How ForexMatch works" };

const STEPS: Array<[string, string]> = [
  [
    "The agent understands your situation",
    "It reads what you write, infers what it can, and asks only the questions that would actually change the answer. Estimates are fine — a range stays a range.",
  ],
  [
    "It searches verified card data",
    "Fees come from providers' own published schedules, stored with the URL they came from and the date they were checked. Nothing is recalled from memory.",
  ],
  [
    "It fetches today's reference rate",
    "A mid-market rate, clearly labelled as such. It is not the rate an issuer will give you, and we never present it as one.",
  ],
  [
    "Code calculates your expected cost",
    "Issuance, reloads, ATM withdrawals and cross-currency charges are priced against your actual usage by a deterministic calculator — not by a language model.",
  ],
  [
    "Code ranks the cards",
    "Six weighted components, using your priorities. The same inputs always produce the same ranking, and the model cannot override it.",
  ],
  [
    "The agent explains the result",
    "Why this card, what it costs, what would change the answer, and what the alternatives are better at.",
  ],
];

export default function About() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/" className="text-sm text-slate-600 underline underline-offset-2 dark:text-slate-400">
        ← Back
      </Link>

      <h1 className="mt-6 text-2xl font-semibold tracking-tight">How ForexMatch works</h1>

      <ol className="mt-6 space-y-5">
        {STEPS.map(([title, body], index) => (
          <li key={title} className="flex gap-4">
            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-medium text-white dark:bg-slate-100 dark:text-slate-900">
              {index + 1}
            </span>
            <div>
              <h2 className="font-medium">{title}</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{body}</p>
            </div>
          </li>
        ))}
      </ol>

      <section className="mt-10">
        <h2 className="text-lg font-medium">What we do with missing data</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Not every provider publishes every charge. When one does not, we do not treat the gap as
          zero — a card must never look cheap because its issuer was quiet. Instead the highest
          charge among the cards being compared is substituted, the line is flagged, and the
          reasoning is shown in the cost breakdown. Where a provider states a charge is genuinely
          nil, that is recorded as a different fact and shown as free.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium">What this is not</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          This is an informational comparison, not financial advice. Fees, exchange rates and product
          terms change. Always check the provider&apos;s current terms before applying. ForexMatch
          does not issue cards, process applications, or ask for KYC documents.
        </p>
      </section>
    </main>
  );
}
