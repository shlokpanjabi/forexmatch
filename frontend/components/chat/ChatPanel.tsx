"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE, ApiRequestError, ApiUnreachableError, streamChat } from "@/lib/api";
import type { ChatMessage, Profile, Recommendation, ToolEvent } from "@/lib/types";
import { AgentActivity } from "@/components/activity/AgentActivity";
import { Results } from "@/components/results/Results";
import { ProfileSummary } from "./ProfileSummary";

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
    <div className="mx-auto w-full max-w-3xl px-4 pb-28">
      {!started && (
        <div className="py-8">
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
            Tell me where you&apos;re going, roughly how you&apos;ll spend, and what matters to you.
          </p>
          <div className="space-y-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => void send(example)}
                className="block w-full rounded-lg border border-slate-200 bg-white p-3 text-left text-sm text-slate-700 transition hover:border-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600"
              >
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
              <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2.5 text-sm text-white dark:bg-slate-100 dark:text-slate-900">
                {message.content}
              </p>
            </div>
          ) : (
            <div key={message.id} className="flex justify-start">
              <div className="max-w-[92%] whitespace-pre-wrap text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                {message.content}
                {message.pending && !message.content && (
                  <span className="text-slate-400 dark:text-slate-500">Thinking…</span>
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
            className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-900 dark:bg-amber-950"
          >
            <p className="font-medium text-amber-900 dark:text-amber-200">
              The ForexMatch API isn&apos;t reachable
            </p>
            <p className="mt-1 text-amber-800 dark:text-amber-300">
              This page is deployed, but its backend — the card database, the exchange-rate
              service and the recommendation engine — is not yet publicly hosted, so the
              assistant can&apos;t run.
            </p>
            <p className="mt-2 text-amber-800 dark:text-amber-300">
              Running it yourself? Start the API with{" "}
              <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-xs dark:bg-amber-900">
                ./scripts/dev.sh
              </code>{" "}
              and reload. This page expects it at{" "}
              <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-xs dark:bg-amber-900">
                {API_BASE}
              </code>
              .
            </p>
            <p className="mt-2">
              <a
                href="https://github.com/shlokpanjabi/forexmatch"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-900 underline underline-offset-2 dark:text-amber-200"
              >
                Source and setup instructions
              </a>
            </p>
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
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
        className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white/95 p-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95"
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
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-slate-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            {busy ? "…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
