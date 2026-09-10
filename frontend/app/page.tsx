import Link from "next/link";

import { getCatalogueStats } from "@/lib/catalogue";
import { Footer } from "@/components/site/Footer";
import { HeroVisual } from "@/components/site/HeroVisual";
import { Nav } from "@/components/site/Nav";
import { Card, Label, LinkButton, Stat } from "@/components/ui/primitives";

export const revalidate = 3600;

const STEPS = [
  {
    n: "01",
    kind: "Understand",
    title: "Tell us the shape of your year",
    body: "Where you're going, roughly what you'll spend, how often you'll want cash. Estimates are fine — a range stays a range, and we never invent precision you didn't give.",
  },
  {
    n: "02",
    kind: "Research",
    title: "The agent reads the fee schedules",
    body: "It searches the catalogue, pulls each candidate's published charges, and fetches today's reference rate. You watch it work — every step is a real tool call, not a loading animation.",
  },
  {
    n: "03",
    kind: "Compute",
    title: "Code prices your actual usage",
    body: "Issuance, reloads, ATM withdrawals and cross-currency charges, costed against your numbers by a deterministic calculator. The same inputs always produce the same ranking.",
  },
  {
    n: "04",
    kind: "Explain",
    title: "You see the whole calculation",
    body: "Why this card, what it costs, what would change the answer, and where every figure came from. Nothing is hidden behind a score.",
  },
];

const FAQ = [
  {
    q: "Do providers pay to rank higher?",
    a: "No. There are no commissions, referral fees or paid placements, and the ranking code cannot see whether a card has an affiliate link — that is resolved only after a winner has been chosen. If we ever add affiliate links, this page will say so.",
  },
  {
    q: "What happens when a provider doesn't publish a fee?",
    a: "It is recorded as unknown, never as zero. When we price a card with a missing charge, we substitute the highest figure any compared card charges, label that line clearly, and say so in the result. A card must never look cheap because its issuer was quiet.",
  },
  {
    q: "Is this financial advice?",
    a: "No. It is an informational comparison. Fees and terms change, so check the provider's current terms before applying. We cannot issue a card or process an application.",
  },
  {
    q: "What data do you keep about me?",
    a: "Only what the comparison needs: destination, rough spend, how much cash you use, and what you care about. We never ask for a passport number, bank account, card number, PAN or Aadhaar, and there is no login.",
  },
  {
    q: "How current is the card data?",
    a: "Every fact carries the document it came from and the date it was checked, and each card shows its own freshness. Where a figure is aging, the agent says so rather than quoting it with false confidence.",
  },
];

export default async function Home() {
  const stats = await getCatalogueStats();

  return (
    <>
      <Nav />

      <main className="relative">
        {/* ---------------------------------------------------------- hero */}
        <section className="ember-wash relative overflow-hidden">
          <div className="relative z-10 mx-auto max-w-6xl px-5 pb-20 pt-16 sm:pt-20">
            <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_1fr]">
              <div>
                <Label>For Indian students going abroad</Label>

                <h1 className="display mt-5 text-5xl leading-[1.03] sm:text-6xl lg:text-7xl">
                  The forex card that actually <em>fits your year</em>.
                </h1>

                <p className="mt-7 max-w-lg text-lg leading-relaxed text-mist-200">
                  Tell us where you&apos;re going and how you&apos;ll spend. An agent researches the
                  cards, prices them against your real usage, and shows every figure it used.
                </p>

                <div className="mt-9 flex flex-wrap items-center gap-3">
                  <LinkButton href="/pick" size="lg">
                    Find my card →
                  </LinkButton>
                  <LinkButton href="/chat" variant="secondary" size="lg">
                    Or just describe your plans
                  </LinkButton>
                </div>

                <p className="mt-4 font-mono text-[11px] uppercase tracking-widest text-mist-500">
                  About 60 seconds · No login · No commissions
                </p>
              </div>

              <HeroVisual />
            </div>

            <div className="mt-16 grid grid-cols-2 gap-8 border-t border-ink-800 pt-8 sm:grid-cols-4">
              <Stat value={String(stats.cards)} label="Cards priced" />
              <Stat value={String(stats.providers)} label="Providers" />
              <Stat value={`${stats.currencies}+`} label="Currencies" />
              <Stat value="0" label="Commissions" accent />
            </div>
          </div>
        </section>

        {/* ------------------------------------------------- the difference */}
        <section className="mx-auto max-w-6xl px-5 py-20">
          <Label>Why trust this</Label>
          <h2 className="display mt-4 max-w-2xl text-4xl sm:text-5xl">
Most comparison sites rank by commission. <em>This one can&apos;t.</em>
          </h2>

          <div className="mt-12 grid gap-5 md:grid-cols-3">
            <Card className="p-6">
              <p className="display text-2xl">Unknown is never zero</p>
              <p className="mt-3 text-sm leading-relaxed text-mist-400">
                When a provider won&apos;t publish a charge, we substitute the highest fee among the
                cards being compared and label it. A quiet issuer never gets to look cheap.
              </p>
            </Card>
            <Card className="p-6">
              <p className="display text-2xl">The maths is code, not a model</p>
              <p className="mt-3 text-sm leading-relaxed text-mist-400">
                A language model runs the conversation. It cannot choose the winner, reorder results
                or adjust a score — a deterministic engine does that, so the same inputs always give
                the same answer.
              </p>
            </Card>
            <Card className="p-6">
              <p className="display text-2xl">Every figure has a receipt</p>
              <p className="mt-3 text-sm leading-relaxed text-mist-400">
                Each fee links to the provider&apos;s own fee schedule and the date it was verified.
                Nothing is recalled from memory or estimated to fill a gap.
              </p>
            </Card>
          </div>
        </section>

        {/* -------------------------------------------------- how it works */}
        <section className="border-y border-ink-800 bg-ink-900/40">
          <div className="mx-auto max-w-6xl px-5 py-20">
            <Label>How it works</Label>
            <h2 className="display mt-4 text-4xl sm:text-5xl">
              Four steps, <em>all of them visible</em>.
            </h2>

            <ol className="mt-12 grid gap-px overflow-hidden rounded-[--radius-card] border border-ink-800 bg-ink-800 md:grid-cols-2">
              {STEPS.map((step) => (
                <li key={step.n} className="bg-ink-950 p-7">
                  <div className="flex items-baseline gap-3">
                    <span className="display text-2xl text-ember-500">{step.n}</span>
                    <Label>{step.kind}</Label>
                  </div>
                  <p className="display mt-4 text-xl">{step.title}</p>
                  <p className="mt-3 text-sm leading-relaxed text-mist-400">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* --------------------------------------------------------- faq */}
        <section className="mx-auto max-w-3xl px-5 py-20">
          <Label>Questions</Label>
          <h2 className="display mt-4 text-4xl sm:text-5xl">
            The things <em>worth asking</em>.
          </h2>

          <div className="mt-10 divide-y divide-ink-800 border-y border-ink-800">
            {FAQ.map((item) => (
              <details key={item.q} className="group py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-left">
                  <span className="font-medium text-mist-50">{item.q}</span>
                  <span
                    aria-hidden
                    className="shrink-0 font-mono text-lg text-mist-500 transition group-open:rotate-45"
                  >
                    +
                  </span>
                </summary>
                <p className="mt-3 pr-8 text-sm leading-relaxed text-mist-400">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* --------------------------------------------------------- cta */}
        <section className="mx-auto max-w-6xl px-5 pb-4">
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
              <h2 className="display mx-auto max-w-2xl text-4xl sm:text-5xl">
                Find out what your year abroad <em>actually costs</em>.
              </h2>
              <p className="mx-auto mt-4 max-w-md text-mist-400">
                No login, no email, no commission. Just the numbers and where they came from.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <LinkButton href="/pick" size="lg">
                  Find my card →
                </LinkButton>
                <Link
                  href="/cards"
                  className="inline-flex h-12 items-center px-4 text-sm text-mist-400 underline underline-offset-4 transition hover:text-mist-50"
                >
                  Browse all {stats.cards} cards
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
