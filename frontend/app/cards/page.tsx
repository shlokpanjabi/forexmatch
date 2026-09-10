import Link from "next/link";

import { getCards } from "@/lib/catalogue";
import { Footer } from "@/components/site/Footer";
import { Nav } from "@/components/site/Nav";
import { Card, Label, LinkButton, Pill } from "@/components/ui/primitives";

export const revalidate = 3600;

export const metadata = {
  title: "Every card we price — ForexMatch",
  description:
    "The full forex card catalogue, with the fees each provider publishes and the documents they came from.",
};

const FRESHNESS_TONE = {
  fresh: "good",
  recent: "good",
  aging: "caution",
  stale: "caution",
  unknown: "neutral",
} as const;

export default async function CardsPage() {
  const cards = await getCards();
  const providers = [...new Set(cards.map((c) => c.provider))].sort();

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-6xl px-5 py-14">
        <Label>The catalogue</Label>
        <h1 className="display mt-4 max-w-3xl text-4xl sm:text-6xl">
          Every card we price, and where the numbers came from.
        </h1>
        <p className="mt-5 max-w-2xl leading-relaxed text-mist-400">
          {cards.length} products from {providers.length} providers. Each one is priced from the
          provider&apos;s own published material — never an estimate, and never a figure recalled
          from memory. Where a charge is unpublished, we say so rather than filling the gap.
        </p>

        {cards.length === 0 ? (
          <Card className="mt-10 p-6">
            <p className="text-mist-200">The catalogue could not be loaded right now.</p>
            <p className="mt-2 text-sm text-mist-400">
              The API is unreachable. Try again shortly.
            </p>
          </Card>
        ) : (
          <div className="mt-12 space-y-12">
            {providers.map((provider) => (
              <section key={provider}>
                <div className="flex items-baseline gap-3 border-b border-ink-800 pb-3">
                  <h2 className="display text-xl">{provider}</h2>
                  <span className="font-mono text-[11px] uppercase tracking-widest text-mist-500">
                    {cards.filter((c) => c.provider === provider).length} card
                    {cards.filter((c) => c.provider === provider).length === 1 ? "" : "s"}
                  </span>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {cards
                    .filter((c) => c.provider === provider)
                    .map((card) => (
                      <Link key={card.id} href={`/cards/${card.slug}`} className="group">
                        <Card className="h-full p-5 transition group-hover:border-ink-600">
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="text-base font-medium leading-snug text-mist-50">
                              {card.card_name}
                            </h3>
                            <Pill tone={FRESHNESS_TONE[card.freshness]}>{card.freshness}</Pill>
                          </div>

                          {card.description && (
                            <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-mist-400">
                              {card.description}
                            </p>
                          )}

                          <div className="mt-4 border-t border-ink-800 pt-3">
                            {card.currency_support_verified ? (
                              <p className="font-mono text-[11px] uppercase tracking-wider text-mist-500">
                                {card.supported_currencies.length} currencies ·{" "}
                                {card.supported_currencies.slice(0, 4).join(" ")}
                                {card.supported_currencies.length > 4 && " …"}
                              </p>
                            ) : (
                              <p className="font-mono text-[11px] uppercase tracking-wider text-amber-400">
                                Currency list unverified
                              </p>
                            )}
                          </div>
                        </Card>
                      </Link>
                    ))}
                </div>
              </section>
            ))}
          </div>
        )}

        <div className="mt-16 border-t border-ink-800 pt-10 text-center">
          <h2 className="display text-2xl">Which of these actually fits you?</h2>
          <p className="mx-auto mt-3 max-w-md text-sm text-mist-400">
            A list is not an answer. Six questions and we&apos;ll price every one of them against
            your year.
          </p>
          <LinkButton href="/pick" size="lg" className="mt-6">
            Find my card →
          </LinkButton>
        </div>
      </main>
      <Footer />
    </>
  );
}
