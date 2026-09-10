import Link from "next/link";

import { getCatalogueStats } from "@/lib/catalogue";
import { Footer } from "@/components/site/Footer";
import { Nav } from "@/components/site/Nav";
import { Card, Label, LinkButton, Pill } from "@/components/ui/primitives";

export const revalidate = 3600;

export const metadata = {
  title: "How it works — ForexMatch",
  description:
    "An agent reads the fee schedules; deterministic code does the maths. Here is exactly what happens between your question and the answer.",
};

const PIPELINE = [
  {
    n: "01",
    kind: "The agent",
    title: "Understands your situation",
    body: "It reads what you write and infers what it can. “Manchester for a two-year master’s” already gives it the UK, GBP, a student and 24 months, so it will not ask again. It asks only the questions that would change the answer.",
    detail: "Estimates are fine. A range stays a range — it never invents precision you did not give.",
  },
  {
    n: "02",
    kind: "The agent",
    title: "Reads the published fee schedules",
    body: "It searches the catalogue for cards that suit your destination, then pulls each candidate’s charges: issuance, reloads, ATM withdrawals, cross-currency. Every figure carries the document it came from.",
    detail: "You watch it happen. Each line in the activity feed is a real tool call, not an animation.",
  },
  {
    n: "03",
    kind: "The agent",
    title: "Fetches today’s reference rate",
    body: "A mid-market rate from a public source, stamped with the moment it was fetched.",
    detail: "This is not the rate a provider will give you — theirs includes a markup. The two are never presented as the same number.",
  },
  {
    n: "04",
    kind: "The code",
    title: "Prices the cards against your usage",
    body: "A deterministic calculator turns your answers into expected quantities — reloads, withdrawals, total spend — and costs every card against them.",
    detail: "No language model touches the arithmetic. The same inputs always produce the same figures.",
  },
  {
    n: "05",
    kind: "The code",
    title: "Ranks them by what you care about",
    body: "Six weighted components — cost, ATM, currency support, convenience, rewards, security — combined with the priorities you set.",
    detail: "The model cannot pick a different winner, reorder the list, or nudge a score.",
  },
  {
    n: "06",
    kind: "The agent",
    title: "Explains the result",
    body: "Why this card suits you, what it costs, what would change the answer, and what the alternatives are better at.",
    detail: "It explains the ranking. It does not produce it.",
  },
];

export default async function About() {
  const stats = await getCatalogueStats();

  return (
    <>
      <Nav />

      <main className="relative z-10">
        <section className="ember-wash relative overflow-hidden">
          <div className="relative z-10 mx-auto max-w-4xl px-5 pb-16 pt-16">
            <Label>How it works</Label>
            <h1 className="display mt-5 text-5xl leading-[1.05] sm:text-6xl">
              A model runs the conversation. <em>Code runs the maths.</em>
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-relaxed text-mist-200">
              That split is the whole product. Language models are good at understanding a messy
              sentence and explaining a result; they are not a trustworthy place to keep somebody’s
              fee schedule. So they never hold one here.
            </p>
          </div>
        </section>

        {/* -------------------------------------------------- the pipeline */}
        <section className="mx-auto max-w-4xl px-5 py-16">
          <ol className="space-y-px overflow-hidden rounded-[--radius-card] border border-ink-800 bg-ink-800">
            {PIPELINE.map((step) => (
              <li key={step.n} className="bg-ink-950 p-6 sm:p-8">
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className="display text-2xl text-ember-500">{step.n}</span>
                  <Pill tone={step.kind === "The code" ? "neutral" : "accent"}>{step.kind}</Pill>
                </div>
                <h2 className="display mt-4 text-2xl sm:text-3xl">{step.title}</h2>
                <p className="mt-3 max-w-2xl leading-relaxed text-mist-400">{step.body}</p>
                <p className="mt-3 max-w-2xl border-l-2 border-ink-700 pl-4 text-sm leading-relaxed text-mist-500">
                  {step.detail}
                </p>
              </li>
            ))}
          </ol>
        </section>

        {/* --------------------------------------------------- missing data */}
        <section className="border-y border-ink-800 bg-ink-900/40">
          <div className="mx-auto max-w-4xl px-5 py-16">
            <Label>The hard part</Label>
            <h2 className="display mt-4 text-4xl sm:text-5xl">
              What we do when a provider <em>won&apos;t say</em>.
            </h2>
            <p className="mt-6 max-w-2xl leading-relaxed text-mist-400">
              Not every provider publishes every charge. Some describe an ATM fee only as
              &ldquo;minimal&rdquo;. The tempting thing is to treat a blank as a zero — and it is
              exactly wrong, because it rewards the issuers who disclose least.
            </p>

            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {[
                {
                  t: "Nil",
                  tone: "good" as const,
                  d: "The provider states the charge is zero. We show it as free, because it is.",
                },
                {
                  t: "Not published",
                  tone: "caution" as const,
                  d: "They publish no figure. We record it as unknown — never as zero — and say so on the card.",
                },
                {
                  t: "Substituted",
                  tone: "caution" as const,
                  d: "When pricing, we fill the gap with the highest charge among the compared cards, label that line, and flag the total as a lower bound.",
                },
              ].map((item) => (
                <Card key={item.t} className="p-5">
                  <Pill tone={item.tone}>{item.t}</Pill>
                  <p className="mt-3 text-sm leading-relaxed text-mist-400">{item.d}</p>
                </Card>
              ))}
            </div>

            <p className="mt-8 max-w-2xl leading-relaxed text-mist-400">
              A card must never look cheap because its issuer was quiet.
            </p>
          </div>
        </section>

        {/* ---------------------------------------------------- provenance */}
        <section className="mx-auto max-w-4xl px-5 py-16">
          <Label>Provenance</Label>
          <h2 className="display mt-4 text-4xl sm:text-5xl">Every figure has a receipt.</h2>
          <p className="mt-6 max-w-2xl leading-relaxed text-mist-400">
            {stats.cards} products from {stats.providers} providers, each fee stored against the
            provider&apos;s own fee schedule, product page or terms document, with the date it was
            checked. Nothing is estimated to fill a gap and nothing is recalled from memory.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <LinkButton href="/cards" variant="secondary">
              Browse every card
            </LinkButton>
            <LinkButton href="/terms" variant="secondary">
              Data policy &amp; verification dates
            </LinkButton>
          </div>
        </section>

        {/* ---------------------------------------------------------- cta */}
        <section className="mx-auto max-w-4xl px-5 pb-4">
          <Card tone="accent" className="relative overflow-hidden p-10 text-center sm:p-14">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-70"
              style={{
                background:
                  "radial-gradient(60% 120% at 50% 100%, rgba(226,61,46,0.20) 0%, transparent 70%)",
              }}
            />
            <div className="relative">
              <h2 className="display mx-auto max-w-xl text-4xl sm:text-5xl">
                See it <em>work on your numbers</em>.
              </h2>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <LinkButton href="/pick" size="lg">
                  Find my card →
                </LinkButton>
                <Link
                  href="/chat"
                  className="inline-flex h-12 items-center px-4 text-sm text-mist-400 underline underline-offset-4 transition hover:text-mist-50"
                >
                  Or watch the agent do it
                </Link>
              </div>
            </div>
          </Card>
        </section>
      </main>

      <Footer />
    </>
  );
}
