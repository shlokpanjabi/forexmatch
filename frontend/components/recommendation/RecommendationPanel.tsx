"use client";

import { useState } from "react";

import { resolveApplicationUrl } from "@/lib/api";
import { track } from "@/lib/analytics";
import type { CardEvaluation, Recommendation } from "@/lib/types";
import { SourceList } from "@/components/sources/SourceList";
import { CostTable } from "./CostTable";

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  medium: "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

function ApplyButton({
  evaluation,
  sessionId,
  source,
}: {
  evaluation: CardEvaluation;
  sessionId: string | null;
  source: string;
}) {
  const [busy, setBusy] = useState(false);

  if (!evaluation.application_url) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {evaluation.card.provider} does not publish an online application for this card.
      </p>
    );
  }

  async function apply() {
    setBusy(true);
    // Track before leaving, then open the provider's own flow.
    const url = sessionId
      ? await resolveApplicationUrl(evaluation.card.slug, sessionId, source)
      : evaluation.application_url;
    setBusy(false);
    window.open(url ?? evaluation.application_url!, "_blank", "noopener,noreferrer");
  }

  return (
    <button
      type="button"
      onClick={apply}
      disabled={busy}
      className="inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
    >
      {busy ? "Opening…" : "Apply for this card"}
    </button>
  );
}

function Evaluation({
  evaluation,
  sessionId,
  isPrimary,
  isTied,
}: {
  evaluation: CardEvaluation;
  sessionId: string | null;
  isPrimary: boolean;
  isTied: boolean;
}) {
  const { card } = evaluation;

  return (
    <article
      className={
        isPrimary
          ? "rounded-xl border-2 border-slate-900 bg-white p-4 dark:border-slate-100 dark:bg-slate-900"
          : "rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
      }
    >
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {card.provider}
          </p>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{card.card_name}</h3>
        </div>
        <div className="text-right">
          <p className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-100">
            {evaluation.match_score}%
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">match</p>
        </div>
      </header>

      {isTied && (
        <p className="mb-3 rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          Effectively tied with the top pick for your usage.
        </p>
      )}

      {!card.currency_support_verified && (
        <p className="mb-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          We could not verify which currencies this card holds, so its cost estimate assumes the
          worst case.
        </p>
      )}

      {evaluation.best_for.length > 0 && (
        <ul className="mb-3 flex flex-wrap gap-1.5">
          {evaluation.best_for.map((tag) => (
            <li
              key={tag}
              className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300"
            >
              {tag}
            </li>
          ))}
        </ul>
      )}

      {evaluation.key_reasons.length > 0 && (
        <div className="mb-3">
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Why this fits
          </h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700 dark:text-slate-300">
            {evaluation.key_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {evaluation.downsides.length > 0 && (
        <div className="mb-3">
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Worth knowing
          </h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
            {evaluation.downsides.map((downside) => (
              <li key={downside}>{downside}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="mb-3" onToggle={() => track("card_viewed", sessionId, { card_slug: card.slug })}>
        <summary className="cursor-pointer text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200">
          Show the full cost calculation
        </summary>
        <div className="mt-3">
          <CostTable cost={evaluation.estimated_cost} />
        </div>
      </details>

      <div className="mb-3">
        <SourceList sources={evaluation.sources} title={`Sources for ${card.card_name}`} />
      </div>

      <ApplyButton
        evaluation={evaluation}
        sessionId={sessionId}
        source={isPrimary ? "recommendation" : "alternative"}
      />
    </article>
  );
}

export function RecommendationPanel({
  recommendation,
  sessionId,
}: {
  recommendation: Recommendation;
  sessionId: string | null;
}) {
  const winner = recommendation.recommended_card;

  if (!winner) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-700 dark:text-slate-300">
          No card in the catalogue suits this destination and profile yet.
        </p>
        {recommendation.excluded.length > 0 && (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
            {recommendation.excluded.map((card) => (
              <li key={card.card_name}>
                {card.card_name} — {card.reason}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  const tied = new Set(recommendation.tied_with_recommended);

  return (
    <section aria-label="Recommendation" className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Best match
        </h2>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            CONFIDENCE_STYLES[recommendation.confidence]
          }`}
        >
          {recommendation.confidence} confidence
        </span>
      </div>

      <Evaluation evaluation={winner} sessionId={sessionId} isPrimary isTied={false} />

      {recommendation.confidence_reasons.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
          {recommendation.confidence_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}

      {recommendation.alternatives.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Alternatives
          </h2>
          {recommendation.alternatives.map((alternative) => (
            <Evaluation
              key={alternative.card.id}
              evaluation={alternative}
              sessionId={sessionId}
              isPrimary={false}
              isTied={tied.has(alternative.card.id)}
            />
          ))}
        </div>
      )}

      {recommendation.assumptions.length > 0 && (
        <details className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
          <summary className="cursor-pointer text-slate-600 dark:text-slate-400">
            What we assumed about you ({recommendation.assumptions.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600 dark:text-slate-400">
            {recommendation.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </details>
      )}

      {recommendation.excluded.length > 0 && (
        <details className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
          <summary className="cursor-pointer text-slate-600 dark:text-slate-400">
            Cards ruled out ({recommendation.excluded.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600 dark:text-slate-400">
            {recommendation.excluded.map((card) => (
              <li key={card.card_name}>
                <strong className="font-medium">{card.card_name}</strong> — {card.reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-900 dark:text-slate-400">
        {recommendation.disclaimer}
      </p>
    </section>
  );
}
