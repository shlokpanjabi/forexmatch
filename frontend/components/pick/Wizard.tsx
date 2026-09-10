"use client";

import { useCallback, useMemo, useState } from "react";

import { fetchRecommendation } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import { Results } from "@/components/results/Results";
import { Button, Label } from "@/components/ui/primitives";
import {
  ATM_USAGE,
  CURRENCY_SPREAD,
  DESTINATIONS,
  DURATIONS,
  PRIORITIES,
  TOTAL_STEPS,
  type Answers,
  type Destination,
  spendBandsFor,
  toProfile,
} from "./questions";

function newSessionId(): string {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

/** One selectable answer. Big target, keyboard reachable, obvious when chosen. */
function Option({
  label,
  hint,
  selected,
  onSelect,
}: {
  label: string;
  hint?: string;
  selected?: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group rounded-xl border p-5 text-left transition ${
        selected
          ? "border-ember-500 bg-ember-600/10"
          : "border-ink-800 bg-ink-900 hover:border-ink-600"
      }`}
    >
      <span className="block text-base font-medium text-mist-50">{label}</span>
      {hint && <span className="mt-1 block text-sm text-mist-400">{hint}</span>}
    </button>
  );
}

function Progress({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-1.5" aria-hidden>
      {Array.from({ length: TOTAL_STEPS }, (_, i) => (
        <span
          key={i}
          className={`h-0.5 flex-1 rounded-full transition-colors ${
            i < step ? "bg-ember-500" : "bg-ink-700"
          }`}
        />
      ))}
    </div>
  );
}

export function Wizard() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [result, setResult] = useState<Recommendation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(newSessionId);

  const submit = useCallback(
    async (finalAnswers: Answers) => {
      setBusy(true);
      setError(null);
      try {
        setResult(await fetchRecommendation(toProfile(finalAnswers), sessionId));
      } catch (caught) {
        setError(
          caught instanceof Error
            ? caught.message
            : "The comparison could not be completed. Please try again.",
        );
      } finally {
        setBusy(false);
      }
    },
    [sessionId],
  );

  // Choosing an answer advances; the last choice submits. No separate Next to
  // press, which is what makes the flow feel quick.
  const choose = useCallback(
    (patch: Partial<Answers>) => {
      const next = { ...answers, ...patch };
      setAnswers(next);
      if (step === TOTAL_STEPS - 1) {
        void submit(next);
      } else {
        setStep((s) => s + 1);
      }
    },
    [answers, step, submit],
  );

  const steps = useMemo(
    () => [
      {
        eyebrow: "Destination",
        question: "Where are you going?",
        body: (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {DESTINATIONS.map((destination: Destination) => (
              <Option
                key={destination.id}
                label={destination.country}
                hint={destination.currency}
                selected={answers.destination?.id === destination.id}
                onSelect={() => choose({ destination })}
              />
            ))}
          </div>
        ),
      },
      {
        eyebrow: "Length of stay",
        question: "How long will you be there?",
        body: (
          <div className="grid gap-3 sm:grid-cols-2">
            {DURATIONS.map((choice) => (
              <Option
                key={choice.value}
                label={choice.label}
                hint={choice.hint}
                selected={answers.duration === choice.value}
                onSelect={() => choose({ duration: choice.value })}
              />
            ))}
          </div>
        ),
      },
      {
        eyebrow: "Spending",
        question: "Roughly how much a month?",
        note: answers.destination
          ? `Rough ranges for ${answers.destination.country}. An estimate is fine — we keep it as a range and never pretend it's exact.`
          : "An estimate is fine. We keep it as a range and never pretend it's exact.",
        body: (
          <div className="grid gap-3 sm:grid-cols-2">
            {spendBandsFor(answers.destination).map((band) => (
              <Option
                key={band.value}
                label={band.label}
                hint={band.hint}
                selected={answers.spend?.value === band.value}
                onSelect={() => choose({ spend: band })}
              />
            ))}
          </div>
        ),
      },
      {
        eyebrow: "Cash",
        question: "How often will you take out cash?",
        note: "ATM charges are where forex cards differ most, so this moves the ranking a lot.",
        body: (
          <div className="grid gap-3 sm:grid-cols-2">
            {ATM_USAGE.map((choice) => (
              <Option
                key={choice.value}
                label={choice.label}
                hint={choice.hint}
                selected={answers.atm === choice.value}
                onSelect={() => choose({ atm: choice.value })}
              />
            ))}
          </div>
        ),
      },
      {
        eyebrow: "Currencies",
        question: "One country, or several?",
        body: (
          <div className="grid gap-3 sm:grid-cols-2">
            {CURRENCY_SPREAD.map((choice) => (
              <Option
                key={choice.value}
                label={choice.label}
                hint={choice.hint}
                selected={answers.spread === choice.value}
                onSelect={() => choose({ spread: choice.value })}
              />
            ))}
          </div>
        ),
      },
      {
        eyebrow: "Priorities",
        question: "What matters most to you?",
        note: "This sets the weights the ranking uses. You can change it afterwards.",
        body: (
          <div className="grid gap-3 sm:grid-cols-2">
            {PRIORITIES.map((choice) => (
              <Option
                key={choice.value}
                label={choice.label}
                hint={choice.hint}
                selected={answers.priority?.value === choice.value}
                onSelect={() => choose({ priority: choice })}
              />
            ))}
          </div>
        ),
      },
    ],
    [answers, choose],
  );

  if (result) {
    return (
      <div className="mx-auto max-w-4xl px-5 py-10">
        <Results
          recommendation={result}
          sessionId={sessionId}
          onRestart={() => {
            setResult(null);
            setAnswers({});
            setStep(0);
          }}
        />
      </div>
    );
  }

  if (busy) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center px-5 text-center">
        <span
          aria-hidden
          className="size-8 animate-spin rounded-full border-2 border-ink-700 border-t-ember-500"
        />
        <p className="display mt-6 text-2xl">Pricing every card against your year</p>
        <p className="mt-2 text-sm text-mist-400">
          Fetching today&apos;s reference rate and running the cost model.
        </p>
      </div>
    );
  }

  const current = steps[step];

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-73px)] max-w-3xl flex-col px-5">
      <div className="flex-1 py-12">
        <Label>
          {String(step + 1).padStart(2, "0")} / {String(TOTAL_STEPS).padStart(2, "0")} ·{" "}
          {current.eyebrow}
        </Label>

        <h1 className="display mt-4 text-4xl sm:text-5xl">{current.question}</h1>
        {current.note && <p className="mt-3 max-w-xl text-sm text-mist-400">{current.note}</p>}

        <div className="mt-9">{current.body}</div>

        {error && (
          <p
            role="alert"
            className="mt-6 rounded-lg border border-ember-600/50 bg-ember-600/10 p-4 text-sm text-ember-300"
          >
            {error}
          </p>
        )}
      </div>

      <div className="sticky bottom-0 space-y-3 border-t border-ink-800 bg-ink-950/95 py-4 backdrop-blur">
        <Progress step={step} />
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
          >
            ← Back
          </Button>
          <span className="font-mono text-[11px] uppercase tracking-widest text-mist-500">
            Pick one to continue
          </span>
        </div>
      </div>
    </div>
  );
}
