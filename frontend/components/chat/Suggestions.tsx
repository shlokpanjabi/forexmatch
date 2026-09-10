"use client";

import type { Recommendation } from "@/lib/types";

/**
 * Follow-ups worth offering.
 *
 * Each one is a genuine re-rank the engine can answer — changing cash usage,
 * priorities or trip length all move the ranking — rather than filler prompts.
 * They are drawn from the result so they name the user's actual alternatives.
 */
export function buildSuggestions(recommendation: Recommendation | null): string[] {
  if (!recommendation?.recommended_card) {
    return [
      "I'm going to the UK for a two-year master's",
      "What's the cheapest card for Germany?",
      "I'll be in the US and want lounge access",
    ];
  }

  const runnerUp = recommendation.comparison.find(
    (e) => e.card.id !== recommendation.recommended_card!.card.id,
  );

  const suggestions = [
    "What if I take out cash every week?",
    "I care more about rewards than fees",
  ];
  if (runnerUp) suggestions.push(`Why not the ${runnerUp.card.card_name}?`);
  suggestions.push("What if I stay an extra year?");
  return suggestions;
}

export function Suggestions({
  suggestions,
  onPick,
  disabled,
}: {
  suggestions: string[];
  onPick: (text: string) => void;
  disabled?: boolean;
}) {
  if (suggestions.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {suggestions.map((text) => (
        <button
          key={text}
          type="button"
          disabled={disabled}
          onClick={() => onPick(text)}
          className="rounded-full border border-ink-700 bg-ink-900 px-3.5 py-1.5 text-left text-xs text-mist-200 transition hover:border-ember-600/60 hover:text-mist-50 disabled:opacity-40"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
