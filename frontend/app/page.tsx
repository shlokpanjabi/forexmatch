import Link from "next/link";

import { ChatPanel } from "@/components/chat/ChatPanel";

export default function Home() {
  return (
    <main>
      <header className="border-b border-slate-200 dark:border-slate-800">
        <div className="mx-auto max-w-3xl px-4 py-6">
          <h1 className="text-xl font-semibold tracking-tight">ForexMatch</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Tell us where you&apos;re going, how you&apos;ll spend, and what matters to you.
            We&apos;ll find the forex card that fits.
          </p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-500">
            Comparisons are built from providers&apos; published fee schedules and today&apos;s
            reference rates. Every figure links to its source.{" "}
            <Link href="/about" className="underline underline-offset-2">
              How this works
            </Link>
          </p>
        </div>
      </header>
      <ChatPanel />
    </main>
  );
}
