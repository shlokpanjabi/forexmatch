"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE, ApiRequestError, ApiUnreachableError, streamChat } from "@/lib/api";
import type { ChatMessage, Profile, Recommendation, ToolEvent } from "@/lib/types";
import { AgentActivity } from "@/components/activity/AgentActivity";
import { Results } from "@/components/results/Results";
import { AgentMark } from "./AgentMark";
import { AgentMessage } from "./AgentMessage";
import { ProfileSummary } from "./ProfileSummary";
import { Suggestions, buildSuggestions } from "./Suggestions";

const EXAMPLES = [
  "I'm an Indian student going to the UK for a two year master's. I'll probably spend around £1,000 to £1,200 a month. I won't withdraw much cash and I mainly care about keeping fees low.",
  "Moving to Germany for a one-year master's, maybe €900 a month. Not sure how much cash I'll need.",
  "I'll be in the US for two years, about $1,500 a month, and I'd like lounge access.",
];

function newId(): string {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiUnreachable, setApiUnreachable] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, toolEvents, recommendation]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;

      setError(null);
      setApiUnreachable(false);
      setBusy(true);
      setToolEvents([]);
      setInput("");

      const assistantId = newId();
      setMessages((current) => [
        ...current,
        { id: newId(), role: "user", content: trimmed },
        { id: assistantId, role: "assistant", content: "", pending: true },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of streamChat(trimmed, sessionId, controller.signal)) {
          switch (event.type) {
            case "session":
              setSessionId(event.session_id);
              break;
            case "tool_event":
              // Replace the "started" row when the same call completes.
              setToolEvents((current) => {
                const index = current.findIndex((e) => e.id === event.event.id);
                if (index === -1) return [...current, event.event];
                const next = [...current];
                next[index] = event.event;
                return next;
              });
              break;
            case "text":
              setMessages((current) =>
                current.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + event.text } : m,
                ),
              );
              break;
            case "profile":
              setProfile(event.profile);
              break;
            case "recommendation":
              setRecommendation(event.recommendation);
              break;
            case "error":
              setError(event.error.message);
              break;
            case "done":
              setMessages((current) =>
                current.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: event.message || m.content, pending: false }
                    : m,
                ),
              );
              break;
          }
        }
      } catch (caught) {
        if ((caught as Error)?.name === "AbortError") return;
        if (caught instanceof ApiUnreachableError) {
          setApiUnreachable(true);
        } else {
          setError(
            caught instanceof ApiRequestError
              ? caught.message
              : "Something went wrong. Please try again.",
          );
        }
      } finally {
        setBusy(false);
        setMessages((current) => current.map((m) => ({ ...m, pending: false })));
        abortRef.current = null;
      }
    },
    [busy, sessionId],
  );

  const started = messages.length > 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-5 pb-32">
      {!started && (
        <div className="py-8">
          <div className="flex gap-3">
            <AgentMark />
            <p className="max-w-lg text-sm leading-relaxed text-mist-300">
              Tell me where you&apos;re going, roughly how you&apos;ll spend, and what matters to
              you. I&apos;ll read the providers&apos; fee schedules, price each card against your
              year, and show you the working.
            </p>
          </div>

          <p className="label mt-8">Try one of these</p>
          <div className="mt-3 space-y-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => void send(example)}
                className="group block w-full rounded-xl border border-ink-800 bg-ink-900 p-4 text-left text-sm leading-relaxed text-mist-300 transition hover:border-ink-600 hover:text-mist-50"
              >
                <span className="mr-2 font-mono text-ember-500 opacity-0 transition group-hover:opacity-100">
                  →
                </span>
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4 py-4">
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex justify-end">
              <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md border border-ink-700 bg-ink-850 px-4 py-2.5 text-sm leading-relaxed text-mist-100">
                {message.content}
              </p>
            </div>
          ) : (
            <div key={message.id} className="flex gap-3">
              <AgentMark busy={message.pending} />
              <div className="min-w-0 max-w-[92%]">
                {message.content && <AgentMessage content={message.content} />}
                {message.pending && !message.content && (
                  <span className="text-sm text-mist-500">Reading the fee schedules…</span>
                )}
                {message.pending && message.content && (
                  <span
                    aria-hidden
                    className="mt-1 inline-block h-4 w-[2px] animate-pulse bg-ember-500"
                  />
                )}
              </div>
            </div>
          ),
        )}

        {toolEvents.length > 0 && <AgentActivity events={toolEvents} />}

        {profile && <ProfileSummary profile={profile} />}

        {recommendation && <Results recommendation={recommendation} sessionId={sessionId} />}

        {apiUnreachable && (
          <div
            role="alert"
            className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-5 text-sm"
          >
            <p className="font-medium text-amber-400">
              The ForexMatch API isn&apos;t reachable
            </p>
            <p className="mt-2 leading-relaxed text-amber-400/80">
              This page is deployed, but its backend — the card database, the exchange-rate
              service and the recommendation engine — is not yet publicly hosted, so the
              assistant can&apos;t run.
            </p>
            <p className="mt-3 leading-relaxed text-amber-400/80">
              Running it yourself? Start the API with{" "}
              <code className="rounded bg-amber-400/15 px-1.5 py-0.5 font-mono text-xs">
                ./scripts/dev.sh
              </code>{" "}
              and reload. This page expects it at{" "}
              <code className="rounded bg-amber-400/15 px-1.5 py-0.5 font-mono text-xs">
                {API_BASE}
              </code>
              .
            </p>
            <p className="mt-2">
              <a
                href="https://github.com/shlokpanjabi/forexmatch"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 underline underline-offset-4"
              >
                Source and setup instructions
              </a>
            </p>
          </div>
        )}

        {!busy && started && (
          <div className="pt-1">
            <Suggestions
              suggestions={buildSuggestions(recommendation)}
              onPick={(text) => void send(text)}
              disabled={busy}
            />
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-xl border border-ember-600/40 bg-ember-600/10 p-4 text-sm text-ember-300"
          >
            {error}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(submitEvent) => {
          submitEvent.preventDefault();
          void send(input);
        }}
        className="fixed inset-x-0 bottom-0 z-20 border-t border-ink-800 bg-ink-950/90 p-4 backdrop-blur"
      >
        <div className="mx-auto flex max-w-3xl gap-2">
          <label htmlFor="message" className="sr-only">
            Message
          </label>
          <input
            id="message"
            value={input}
            onChange={(changeEvent) => setInput(changeEvent.target.value)}
            placeholder={
              started ? "Anything else? You can change your answers too." : "Where are you going?"
            }
            disabled={busy}
            autoComplete="off"
            className="h-11 flex-1 rounded-xl border border-ink-700 bg-ink-900 px-4 text-sm text-mist-50 outline-none transition placeholder:text-mist-500 focus:border-ember-600/70 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="h-11 rounded-xl bg-ember-600 px-5 text-sm font-medium text-white transition hover:bg-ember-500 disabled:opacity-40"
          >
            {busy ? "…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
