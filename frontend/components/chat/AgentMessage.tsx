"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * The agent's reply, rendered.
 *
 * It writes Markdown — headings, bold figures, comparison tables — and showing
 * that raw was making the most substantive part of the product look like debug
 * output.
 *
 * Raw HTML is deliberately not enabled. The model's output is untrusted text,
 * and react-markdown escapes it by default; keeping it that way means a reply
 * can never inject markup into the page.
 */
export function AgentMessage({ content }: { content: string }) {
  return (
    <div className="min-w-0 max-w-none text-sm leading-relaxed text-mist-200">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h3 className="display mt-6 text-2xl text-mist-50 first:mt-0">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="display mt-6 text-2xl text-mist-50 first:mt-0">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="label mt-6 block first:mt-0">{children}</h4>
          ),
          p: ({ children }) => <p className="mt-3 first:mt-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-mist-50">{children}</strong>
          ),
          em: ({ children }) => <em className="italic text-mist-100">{children}</em>,
          ul: ({ children }) => <ul className="mt-3 space-y-1.5">{children}</ul>,
          ol: ({ children }) => <ol className="mt-3 space-y-1.5">{children}</ol>,
          li: ({ children }) => (
            <li className="flex gap-2.5">
              <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-ember-600" />
              <span className="min-w-0 flex-1">{children}</span>
            </li>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-ember-400 underline underline-offset-4 transition hover:text-ember-300"
            >
              {children}
            </a>
          ),
          hr: () => <div className="rule my-6" />,
          code: ({ children }) => (
            <code className="rounded bg-ink-850 px-1.5 py-0.5 font-mono text-xs text-mist-100">
              {children}
            </code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mt-4 border-l-2 border-ember-600/60 pl-4 text-mist-300">
              {children}
            </blockquote>
          ),
          // The agent often compares cards in a table; it must stay readable on
          // a phone, so it scrolls inside its own box rather than the page.
          table: ({ children }) => (
            <div className="mt-4 overflow-x-auto rounded-xl border border-ink-800">
              <table className="w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-ink-850">{children}</thead>,
          th: ({ children }) => (
            <th className="whitespace-nowrap border-b border-ink-800 px-3 py-2.5 font-mono text-[10px] uppercase tracking-wider text-mist-500">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="tnum border-b border-ink-800 px-3 py-2.5 align-top text-mist-200">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
