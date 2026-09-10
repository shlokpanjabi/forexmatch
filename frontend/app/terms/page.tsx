import Link from "next/link";

import { getCards, getCatalogueStats } from "@/lib/catalogue";
import { Footer } from "@/components/site/Footer";
import { Nav } from "@/components/site/Nav";
import { Card, Label, Pill } from "@/components/ui/primitives";

export const revalidate = 3600;

export const metadata = {
  title: "Terms & data policy — ForexMatch",
  description:
    "What ForexMatch is, how the card data is sourced and verified, when it was last checked, and what we do and do not collect.",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

const FRESHNESS_WINDOWS = [
  ["Fresh", "Under 7 days old", "good"],
  ["Recent", "7 to 30 days", "good"],
  ["Aging", "30 to 90 days", "caution"],
  ["Stale", "Over 90 days", "caution"],
] as const;

export default async function TermsPage() {
  const [stats, cards] = await Promise.all([getCatalogueStats(), getCards()]);

  const byFreshness = cards.reduce<Record<string, number>>((acc, card) => {
    acc[card.freshness] = (acc[card.freshness] ?? 0) + 1;
    return acc;
  }, {});

  const oldest = cards
    .map((c) => c.last_verified_at)
    .filter((d): d is string => Boolean(d))
    .sort()[0];

  return (
    <>
      <Nav />
      <main className="relative z-10 mx-auto max-w-3xl px-5 py-14">
        <Label>Terms &amp; data policy</Label>
        <h1 className="display mt-4 text-4xl sm:text-6xl">
          What this is, and <em>when we last checked</em>.
        </h1>

        {/* --------------------------------------------------- freshness */}
        <Card className="mt-10 p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <Label>Catalogue last verified</Label>
              <p className="display mt-1.5 text-3xl">{formatDate(stats.lastVerified)}</p>
            </div>
            <Pill tone={stats.live ? "good" : "caution"}>
              {stats.live ? "Read live from the catalogue" : "Cached figures"}
            </Pill>
          </div>

          <div className="rule my-6" />

          <dl className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <div>
              <dt className="label">Cards</dt>
              <dd className="tnum mt-1 text-2xl">{stats.cards}</dd>
            </div>
            <div>
              <dt className="label">Providers</dt>
              <dd className="tnum mt-1 text-2xl">{stats.providers}</dd>
            </div>
            <div>
              <dt className="label">Within 30 days</dt>
              <dd className="tnum mt-1 text-2xl">{stats.freshCards}</dd>
            </div>
            <div>
              <dt className="label">Oldest check</dt>
              <dd className="tnum mt-1 text-sm text-mist-200">{formatDate(oldest ?? null)}</dd>
            </div>
          </dl>

          <p className="mt-6 text-sm leading-relaxed text-mist-400">
            These figures are read from the live catalogue when this page is built, not typed in by
            hand, so they cannot drift from what the comparison actually uses. Every individual card
            page carries its own verification date and links to the documents behind it.
          </p>
        </Card>

        {/* -------------------------------------------------- how we age it */}
        <section className="mt-14">
          <h2 className="display text-2xl">How we describe age</h2>
          <p className="mt-3 text-sm leading-relaxed text-mist-400">
            Card data does not stop being useful the day after it is checked, but it does get less
            certain. Rather than hide that, every card is bucketed and labelled.
          </p>
          <div className="mt-6 overflow-hidden rounded-[--radius-card] border border-ink-800">
            <table className="w-full text-sm">
              <tbody>
                {FRESHNESS_WINDOWS.map(([name, window, tone]) => (
                  <tr key={name} className="border-b border-ink-800 last:border-0">
                    <td className="w-28 py-3 pl-5">
                      <Pill tone={tone}>{name}</Pill>
                    </td>
                    <td className="py-3 text-mist-400">{window}</td>
                    <td className="tnum py-3 pr-5 text-right text-mist-200">
                      {byFreshness[name.toLowerCase()] ?? 0} card
                      {(byFreshness[name.toLowerCase()] ?? 0) === 1 ? "" : "s"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ---------------------------------------------------- the rules */}
        <div className="mt-14 space-y-10">
          {[
            {
              h: "This is not financial advice",
              p: "ForexMatch is an informational comparison tool. Card rankings, cost estimates and fee figures are for information only and do not constitute financial, credit or investment advice. Fees, exchange rates and product terms change frequently — always verify directly with the provider before applying.",
            },
            {
              h: "Where the numbers come from",
              p: "Every fee, limit, benefit and supported currency is recorded against the provider's own published material — a fee schedule, product page or terms document — together with the URL and the date it was checked. Nothing is estimated to fill a gap, and nothing is recalled from a language model's memory. Where a provider publishes no figure, we record it as unknown rather than as zero.",
            },
            {
              h: "How an unknown charge is handled",
              p: "A card with an unpublished fee must not appear cheaper than one that discloses everything. When we price such a card, we substitute the highest figure charged by any card in the same comparison, label that line explicitly, and say so in the result. The total is then flagged as a lower bound.",
            },
            {
              h: "We take no commission",
              p: "There are no referral fees, affiliate deals or paid placements, and no provider can pay for a better position. The ranking code cannot see whether a card has an affiliate link — that is resolved only after a winner has been chosen. If this ever changes, it will be disclosed here and on the result itself.",
            },
            {
              h: "What we collect",
              p: "Only what the comparison needs: destination, an approximate monthly spend, how much cash you expect to use, and what you care about. There is no login. We never ask for a passport number, bank account, card number, PAN or Aadhaar, and we could not use them if you sent them.",
            },
            {
              h: "Reference rates are not provider rates",
              p: "Exchange rates shown are mid-market reference rates from a public source, labelled as such and stamped with the time they were fetched. The rate a provider gives you includes their own markup and will differ. We never present one as the other.",
            },
          ].map((item) => (
            <section key={item.h}>
              <h2 className="display text-2xl">{item.h}</h2>
              <p className="mt-3 text-sm leading-relaxed text-mist-400">{item.p}</p>
            </section>
          ))}
        </div>

        <div className="rule my-12" />

        <p className="text-sm text-mist-500">
          Questions about the data?{" "}
          <a
            href="https://github.com/shlokpanjabi/forexmatch"
            target="_blank"
            rel="noopener noreferrer"
            className="text-mist-200 underline underline-offset-4 transition hover:text-ember-400"
          >
            The whole catalogue and the code that ranks it are public
          </a>
          .{" "}
          <Link href="/cards" className="text-mist-200 underline underline-offset-4 transition hover:text-ember-400">
            Browse every card
          </Link>
          .
        </p>
      </main>
      <Footer />
    </>
  );
}
