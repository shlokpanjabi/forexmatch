import Link from "next/link";
import { notFound } from "next/navigation";

import { getCard, getCards } from "@/lib/catalogue";
import type { Fee } from "@/lib/types";
import { Footer } from "@/components/site/Footer";
import { Nav } from "@/components/site/Nav";
import { CardArt } from "@/components/ui/CardArt";
import { Card, Label, LinkButton, Pill } from "@/components/ui/primitives";

export const revalidate = 3600;

export async function generateStaticParams() {
  const cards = await getCards();
  return cards.map((card) => ({ slug: card.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const card = await getCard(slug);
  if (!card) return { title: "Card not found — ForexMatch" };
  return {
    title: `${card.card_name} — ${card.provider} | ForexMatch`,
    description:
      card.description ??
      `Published fees and supported currencies for the ${card.provider} ${card.card_name}.`,
  };
}

const FEE_LABELS: Record<string, string> = {
  issuance: "Issuance",
  reload: "Reload",
  atm_withdrawal: "ATM withdrawal",
  cross_currency: "Cross-currency",
  balance_enquiry: "Balance enquiry",
  replacement: "Replacement",
  encashment: "Encashment",
  inactivity: "Inactivity",
  transaction: "Per transaction",
  other: "Other",
};

/**
 * How a fee reads depends on which of three states it is in. Keeping that in
 * one place is what stops "unknown" from ever being rendered as free.
 */
function describeFee(fee: Fee): { text: string; tone: "good" | "caution" | "neutral" | "plain" } {
  if (fee.is_waived) return { text: "Nil", tone: "good" };
  if (fee.is_unknown) return { text: "Not published", tone: "caution" };

  const parts: string[] = [];
  if (fee.amount !== null) parts.push(`${fee.currency ?? ""} ${Number(fee.amount).toLocaleString()}`.trim());
  if (fee.percentage !== null) parts.push(`${Number(fee.percentage)}%`);
  if (parts.length === 0) return { text: "Not verified", tone: "caution" };
  return { text: parts.join(" + "), tone: "plain" };
}

export default async function CardPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const card = await getCard(slug);
  if (!card) notFound();

  // Group per-currency rows (ATM, balance enquiry) so the table stays readable.
  const grouped = new Map<string, Fee[]>();
  for (const fee of card.fees) {
    const list = grouped.get(fee.fee_type) ?? [];
    list.push(fee);
    grouped.set(fee.fee_type, list);
  }

  const unknownCount = card.fees.filter((f) => f.is_unknown).length;

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-4xl px-5 py-12">
        <Link
          href="/cards"
          className="font-mono text-[11px] uppercase tracking-widest text-mist-500 transition hover:text-mist-200"
        >
          ← All cards
        </Link>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <Pill>{card.provider}</Pill>
          <Pill tone={card.freshness === "fresh" || card.freshness === "recent" ? "good" : "caution"}>
            {card.freshness}
          </Pill>
          {!card.currency_support_verified && <Pill tone="caution">Currencies unverified</Pill>}
        </div>

        <div className="mt-4 grid gap-8 sm:grid-cols-[1fr_260px] sm:items-start">
          <div>
            <h1 className="display text-4xl sm:text-5xl">{card.card_name}</h1>
            {card.description && (
              <p className="mt-4 max-w-xl leading-relaxed text-mist-400">{card.description}</p>
            )}
          </div>
          <CardArt
            slug={card.slug}
            currencies={card.currencies.filter((c) => c.direct_wallet).map((c) => c.code)}
            className="w-full rounded-xl"
          />
        </div>

        {unknownCount > 0 && (
          <p className="mt-6 rounded-lg border border-amber-400/30 bg-amber-400/5 p-4 text-sm leading-relaxed text-amber-400">
            {card.provider} does not publish {unknownCount} of the charges on this card. Those are
            recorded as unknown, never as zero — and when we price this card against your usage we
            substitute the highest figure among the cards compared, so a missing number can never
            make it look cheap.
          </p>
        )}

        {/* ------------------------------------------------------- fees */}
        <section className="mt-12">
          <Label>Published charges</Label>
          <Card className="mt-4">
            <table className="w-full text-sm">
              <tbody>
                {[...grouped.entries()].map(([type, fees]) => (
                  <tr key={type} className="border-b border-ink-800 last:border-0">
                    <th scope="row" className="w-44 py-4 pl-5 pr-4 text-left align-top font-normal text-mist-200">
                      {FEE_LABELS[type] ?? type.replace(/_/g, " ")}
                    </th>
                    <td className="py-4 pr-5 align-top">
                      {fees.length > 3 ? (
                        <details className="group">
                          <summary className="cursor-pointer list-none text-mist-400 transition hover:text-mist-50">
                            Varies by currency — {fees.length} rates{" "}
                            <span aria-hidden className="font-mono transition group-open:rotate-45">
                              +
                            </span>
                          </summary>
                          <ul className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
                            {fees.map((fee, i) => {
                              const described = describeFee(fee);
                              return (
                                <li key={i} className="tnum flex justify-between gap-2 text-xs">
                                  <span className="text-mist-500">{fee.currency}</span>
                                  <span className="text-mist-200">{described.text}</span>
                                </li>
                              );
                            })}
                          </ul>
                        </details>
                      ) : (
                        <ul className="space-y-2">
                          {fees.map((fee, i) => {
                            const described = describeFee(fee);
                            return (
                              <li key={i}>
                                <span
                                  className={`tnum ${
                                    described.tone === "good"
                                      ? "text-jade-400"
                                      : described.tone === "caution"
                                        ? "text-amber-400"
                                        : "text-mist-50"
                                  }`}
                                >
                                  {described.text}
                                </span>
                                {fee.conditions && (
                                  <span className="mt-0.5 block text-xs leading-relaxed text-mist-500">
                                    {fee.conditions}
                                  </span>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="mt-3 text-xs text-mist-500">
            <span className="text-jade-400">Nil</span> means the provider states the charge is zero.{" "}
            <span className="text-amber-400">Not published</span> means they publish no figure — it
            is not the same thing.
          </p>
        </section>

        {/* -------------------------------------------------- currencies */}
        {card.currencies.length > 0 && (
          <section className="mt-12">
            <Label>Currencies held</Label>
            <div className="mt-4 flex flex-wrap gap-2">
              {card.currencies.map((currency) => (
                <span
                  key={currency.code}
                  className={`rounded-lg border px-3 py-1.5 font-mono text-xs ${
                    currency.direct_wallet
                      ? "border-ink-700 bg-ink-900 text-mist-200"
                      : "border-ink-800 text-mist-500"
                  }`}
                >
                  {currency.code}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* ---------------------------------------------------- benefits */}
        {card.benefits.length > 0 && (
          <section className="mt-12">
            <Label>Documented benefits</Label>
            <ul className="mt-4 space-y-2">
              {card.benefits.map((benefit, i) => (
                <li key={i} className="flex gap-3 text-sm leading-relaxed text-mist-300">
                  <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full bg-ember-600" />
                  <span className="text-mist-200">
                    {benefit.description}
                    {benefit.value && <span className="text-mist-500"> — {benefit.value}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ----------------------------------------------------- sources */}
        <section className="mt-12">
          <Label>Sources</Label>
          <ul className="mt-4 space-y-3">
            {card.sources.map((source) => (
              <li key={source.url} className="text-sm">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-mist-200 underline decoration-ink-600 underline-offset-2 transition hover:text-ember-400"
                >
                  {source.title ?? source.domain}
                </a>
                <span className="ml-2 text-xs text-mist-500">
                  {source.is_official ? "Official" : "Secondary"} · verified{" "}
                  {new Date(source.last_verified_at).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <div className="mt-14 flex flex-wrap items-center gap-4 border-t border-ink-800 pt-8">
          <LinkButton href="/pick" size="lg">
            See if this card fits you →
          </LinkButton>
          {card.application_url && (
            <a
              href={card.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-mist-400 underline underline-offset-4 transition hover:text-mist-50"
            >
              Apply at {card.provider} ↗
            </a>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
