"use client";

import { useState } from "react";

import { track } from "@/lib/analytics";
import { resolveApplicationUrl } from "@/lib/api";
import type { CardEvaluation, Recommendation } from "@/lib/types";
import { CardArt } from "@/components/ui/CardArt";
import { Button, Card, Label, Pill } from "@/components/ui/primitives";

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

function rupees(value: string): string {
  return `₹${inr.format(Number(value))}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

const CONFIDENCE_TONE = { high: "good", medium: "caution", low: "neutral" } as const;

/* ------------------------------------------------------------------ apply */

function ApplyButton({
  evaluation,
  sessionId,
  source,
  variant = "primary",
}: {
  evaluation: CardEvaluation;
  sessionId: string | null;
  source: string;
  variant?: "primary" | "secondary";
}) {
  const [busy, setBusy] = useState(false);

  if (!evaluation.application_url) {
    return (
      <p className="text-sm text-mist-500">
        {evaluation.card.provider} publishes no online application for this card.
      </p>
    );
  }

  async function apply() {
    setBusy(true);
    // Recorded before the user leaves, so the click is never lost.
    const url = sessionId
      ? await resolveApplicationUrl(evaluation.card.slug, sessionId, source)
      : evaluation.application_url;
    setBusy(false);
    window.open(url ?? evaluation.application_url!, "_blank", "noopener,noreferrer");
  }

  return (
    <Button variant={variant} size={variant === "primary" ? "lg" : "md"} onClick={apply} disabled={busy}>
      {busy ? "Opening…" : `Apply at ${evaluation.card.provider} ↗`}
    </Button>
  );
}

/* ------------------------------------------------------------- cost table */

function CostBreakdown({ evaluation }: { evaluation: CardEvaluation }) {
  const cost = evaluation.estimated_cost;
  return (
    <div className="space-y-4">
      <table className="w-full text-sm">
        <caption className="sr-only">
          Estimated charges over {cost.duration_months} months
        </caption>
        <tbody>
          {cost.components.map((component) => (
            <tr key={`${component.fee_type}-${component.label}`} className="border-b border-ink-800 last:border-0">
              <th scope="row" className="py-3 pr-4 text-left align-top font-normal">
                <span className="text-mist-200">{component.label}</span>
                <span className="mt-0.5 block text-xs text-mist-500">{component.basis}</span>
                {component.is_imputed && component.imputation_note && (
                  <span className="mt-2 block rounded-md border border-amber-400/30 bg-amber-400/5 p-2 text-xs leading-relaxed text-amber-400">
                    {component.imputation_note}
                  </span>
                )}
              </th>
              <td className="tnum py-3 text-right align-top text-mist-50">
                {rupees(component.amount_inr)}
              </td>
            </tr>
          ))}
          <tr className="border-t-2 border-ink-700">
            <th scope="row" className="py-3 pr-4 text-left font-medium text-mist-50">
              Total over {cost.duration_months} months
              {cost.total_is_lower_bound && (
                <span className="mt-1 block text-xs font-normal text-amber-400">
                  At least this much — some charges are unpublished on every card compared.
                </span>
              )}
            </th>
            <td className="tnum py-3 text-right font-medium text-mist-50">
              {rupees(cost.total_inr)}
              {cost.total_spend_currency && cost.spend_currency && (
                <span className="mt-0.5 block text-xs font-normal text-mist-500">
                  ≈ {cost.spend_currency} {inr.format(Number(cost.total_spend_currency))}
                </span>
              )}
            </td>
          </tr>
        </tbody>
      </table>

      {cost.fx_rate_used && (
        <p className="text-xs leading-relaxed text-mist-500">
          Converted at a mid-market reference rate of {cost.fx_rate_used}. A provider&apos;s own rate
          includes their markup and will differ.
        </p>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- sources */

function Sources({ evaluation }: { evaluation: CardEvaluation }) {
  if (evaluation.sources.length === 0) return null;
  return (
    <div>
      <Label>Where these figures come from</Label>
      <ul className="mt-3 space-y-2">
        {evaluation.sources.map((source) => (
          <li key={source.url} className="text-sm">
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-mist-200 underline decoration-ink-600 underline-offset-2 transition hover:text-ember-400 hover:decoration-ember-400"
            >
              {source.title ?? source.domain}
            </a>
            <span className="ml-2 text-xs text-mist-500">
              {source.is_official ? "Official" : "Secondary"} · verified{" "}
              {formatDate(source.last_verified_at)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------------------------------------------------------------- winner */

function Winner({
  evaluation,
  sessionId,
  confidence,
  spendCurrency,
}: {
  evaluation: CardEvaluation;
  sessionId: string | null;
  confidence: Recommendation["confidence"];
  spendCurrency: string | null;
}) {
  const { card, estimated_cost: cost } = evaluation;
  const convertsEveryPurchase =
    Boolean(spendCurrency) &&
    card.currency_support_verified &&
    !card.supported_currencies.includes(spendCurrency!);

  return (
    <Card tone="accent" className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-40 opacity-60"
        style={{
          background: "radial-gradient(70% 100% at 50% 0%, rgba(226,61,46,0.18) 0%, transparent 70%)",
        }}
      />
      <div className="relative p-6 sm:p-8">
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="accent">Best match</Pill>
          <Pill tone={CONFIDENCE_TONE[confidence]}>{confidence} confidence</Pill>
          {!card.currency_support_verified && <Pill tone="caution">Currencies unverified</Pill>}
          {convertsEveryPurchase && <Pill tone="caution">Converts every purchase</Pill>}
        </div>

        {convertsEveryPurchase && (
          <p className="mt-5 rounded-lg border border-amber-400/30 bg-amber-400/5 p-4 text-sm leading-relaxed text-amber-400">
            This card does not hold {spendCurrency}. Every purchase is converted from the currency
            it holds, so the rate you get carries {card.provider}&apos;s own markup on top of any
            fee shown below — and that markup is not published, so it is not in this estimate.
          </p>
        )}

        {/* The artwork is decorative, so it drops away on narrow screens while
            the score stays put — one element, not a responsive duplicate. */}
        <div className="mt-5 grid gap-6 sm:grid-cols-[1fr_170px] sm:items-center">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <Label>{card.provider}</Label>
              <h2 className="display mt-1.5 text-3xl sm:text-4xl">{card.card_name}</h2>
            </div>
            <div className="text-right">
              <p className="display tnum text-4xl text-ember-400">{evaluation.match_score}%</p>
              <p className="label mt-0.5">match</p>
            </div>
          </div>
          <CardArt slug={card.slug} compact className="hidden w-full rounded-lg sm:block" />
        </div>

        <div className="mt-7 grid gap-4 border-y border-ink-800 py-6 sm:grid-cols-2">
          <div>
            <Label>Estimated charges</Label>
            <p className="display tnum mt-1.5 text-3xl">{rupees(cost.total_inr)}</p>
            <p className="mt-1 text-xs text-mist-500">
              over {cost.duration_months} months
              {cost.total_spend_currency &&
                cost.spend_currency &&
                ` · ≈ ${cost.spend_currency} ${inr.format(Number(cost.total_spend_currency))}`}
            </p>
          </div>
          {evaluation.best_for.length > 0 && (
            <div>
              <Label>Strengths</Label>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {evaluation.best_for.map((tag) => (
                  <li key={tag}>
                    <Pill>{tag}</Pill>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {evaluation.key_reasons.length > 0 && (
          <div className="mt-6">
            <Label>Why it fits you</Label>
            <ul className="mt-3 space-y-2">
              {evaluation.key_reasons.map((reason) => (
                <li key={reason} className="flex gap-3 text-sm leading-relaxed text-mist-200">
                  <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full bg-ember-500" />
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        {evaluation.downsides.length > 0 && (
          <div className="mt-6">
            <Label>Worth knowing</Label>
            <ul className="mt-3 space-y-2">
              {evaluation.downsides.map((downside) => (
                <li key={downside} className="flex gap-3 text-sm leading-relaxed text-mist-400">
                  <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full bg-ink-600" />
                  {downside}
                </li>
              ))}
            </ul>
          </div>
        )}

        <details
          className="group mt-6 border-t border-ink-800 pt-5"
          onToggle={() => track("card_viewed", sessionId, { card_slug: card.slug })}
        >
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm text-mist-400 transition hover:text-mist-50">
            <span aria-hidden className="font-mono transition group-open:rotate-45">
              +
            </span>
            See the full calculation and sources
          </summary>
          <div className="mt-5 space-y-6">
            <CostBreakdown evaluation={evaluation} />
            <Sources evaluation={evaluation} />
          </div>
        </details>

        <div className="mt-7">
          <ApplyButton evaluation={evaluation} sessionId={sessionId} source="recommendation" />
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------- ranked row */

function RankedRow({
  evaluation,
  rank,
  sessionId,
  tied,
}: {
  evaluation: CardEvaluation;
  rank: number;
  sessionId: string | null;
  tied: boolean;
}) {
  const { card, estimated_cost: cost } = evaluation;

  return (
    <details
      className="group border-b border-ink-800 last:border-0"
      onToggle={() => track("alternative_viewed", sessionId, { card_slug: card.slug })}
    >
      <summary className="flex cursor-pointer list-none items-center gap-4 py-4 transition hover:bg-ink-900/60">
        <span className="tnum w-6 shrink-0 text-center font-mono text-xs text-mist-500">
          {String(rank).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-mist-50">{card.card_name}</span>
          <span className="block truncate text-xs text-mist-500">
            {card.provider}
            {tied && " · effectively tied with the top pick"}
          </span>
        </span>
        <span className="tnum hidden w-28 shrink-0 text-right text-sm text-mist-200 sm:block">
          {rupees(cost.total_inr)}
          {cost.total_is_lower_bound && <span className="text-amber-400">+</span>}
        </span>
        <span className="tnum w-12 shrink-0 text-right text-sm text-mist-400">
          {evaluation.match_score}%
        </span>
        <span aria-hidden className="w-4 shrink-0 text-center font-mono text-mist-600 transition group-open:rotate-45">
          +
        </span>
      </summary>

      <div className="space-y-6 pb-6 pl-10 pr-2">
        {evaluation.key_reasons.length > 0 && (
          <ul className="space-y-1.5">
            {evaluation.key_reasons.map((reason) => (
              <li key={reason} className="text-sm leading-relaxed text-mist-400">
                {reason}
              </li>
            ))}
          </ul>
        )}
        <CostBreakdown evaluation={evaluation} />
        <Sources evaluation={evaluation} />
        <ApplyButton evaluation={evaluation} sessionId={sessionId} source="ranking" variant="secondary" />
      </div>
    </details>
  );
}

/* ----------------------------------------------------------------- shell */

export function Results({
  recommendation,
  sessionId,
  onRestart,
}: {
  recommendation: Recommendation;
  sessionId: string | null;
  onRestart?: () => void;
}) {
  const winner = recommendation.recommended_card;
  const tied = new Set(recommendation.tied_with_recommended);

  if (!winner) {
    return (
      <Card className="p-6">
        <p className="text-mist-200">No card in the catalogue suits this destination and profile.</p>
        {recommendation.excluded.length > 0 && (
          <ul className="mt-3 space-y-1.5 text-sm text-mist-400">
            {recommendation.excluded.map((card) => (
              <li key={card.card_name}>
                {card.card_name} — {card.reason}
              </li>
            ))}
          </ul>
        )}
        {onRestart && (
          <Button variant="secondary" className="mt-5" onClick={onRestart}>
            Start again
          </Button>
        )}
      </Card>
    );
  }

  // The winner is shown in full above, so the table lists the rest.
  const rest = recommendation.comparison.filter((e) => e.card.id !== winner.card.id);

  return (
    <div className="space-y-10">
      <Winner
        evaluation={winner}
        sessionId={sessionId}
        confidence={recommendation.confidence}
        spendCurrency={recommendation.spend_currency}
      />

      {recommendation.confidence_reasons.length > 0 && (
        <div>
          <Label>Why confidence is {recommendation.confidence}</Label>
          <ul className="mt-3 space-y-1.5">
            {recommendation.confidence_reasons.map((reason) => (
              <li key={reason} className="text-sm leading-relaxed text-mist-400">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {rest.length > 0 && (
        <section>
          <div className="flex items-baseline justify-between gap-4">
            <div>
              <Label>Every other eligible card</Label>
              <h3 className="display mt-1.5 text-2xl">Ranked for your usage</h3>
            </div>
            <span className="hidden font-mono text-[11px] uppercase tracking-widest text-mist-500 sm:block">
              cost · match
            </span>
          </div>
          <Card className="mt-5 px-4">
            {rest.map((evaluation, index) => (
              <RankedRow
                key={evaluation.card.id}
                evaluation={evaluation}
                rank={index + 2}
                sessionId={sessionId}
                tied={tied.has(evaluation.card.id)}
              />
            ))}
          </Card>
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {recommendation.assumptions.length > 0 && (
          <Card className="p-5">
            <Label>What we assumed about you</Label>
            <ul className="mt-3 space-y-2">
              {recommendation.assumptions.map((assumption) => (
                <li key={assumption} className="text-sm leading-relaxed text-mist-400">
                  {assumption}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {recommendation.excluded.length > 0 && (
          <Card className="p-5">
            <Label>Cards ruled out</Label>
            <ul className="mt-3 space-y-2">
              {recommendation.excluded.map((card) => (
                <li key={card.card_name} className="text-sm leading-relaxed text-mist-400">
                  <span className="text-mist-200">{card.card_name}</span> — {card.reason}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-ink-800 pt-6">
        {onRestart && (
          <Button variant="secondary" onClick={onRestart}>
            Change my answers
          </Button>
        )}
        <a
          href="/chat"
          className="text-sm text-mist-400 underline underline-offset-4 transition hover:text-mist-50"
        >
          Ask the agent about these results
        </a>
      </div>

      <p className="rounded-lg border border-ink-800 bg-ink-900 p-4 text-xs leading-relaxed text-mist-500">
        {recommendation.disclaimer}
      </p>
    </div>
  );
}
