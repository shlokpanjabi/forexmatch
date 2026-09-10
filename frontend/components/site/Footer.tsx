import Link from "next/link";

import { getCatalogueStats } from "@/lib/catalogue";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export async function Footer() {
  const stats = await getCatalogueStats();

  return (
    <footer className="relative z-10 mt-28 border-t border-ink-800">
      <div className="mx-auto max-w-6xl px-5 py-12">
        <div className="grid gap-10 sm:grid-cols-3">
          <div>
            <div className="flex items-center gap-2">
              <span aria-hidden className="block size-2 rotate-45 bg-ember-500" />
              <span className="display text-lg">ForexMatch</span>
            </div>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-mist-400">
              Every figure comes from a provider&apos;s own published material, stored with the
              document it came from and the date it was checked.
            </p>
          </div>

          <div>
            <p className="label">Explore</p>
            <ul className="mt-3 space-y-2 text-sm">
              {[
                ["/cards", "All cards"],
                ["/pick", "Find my card"],
                ["/chat", "Ask the agent"],
                ["/about", "How it works"],
              ].map(([href, label]) => (
                <li key={href}>
                  <Link href={href} className="text-mist-200 transition hover:text-ember-400">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="label">Data</p>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-4 border-b border-ink-800 pb-2">
                <dt className="text-mist-500">Catalogue verified</dt>
                <dd className="tnum text-mist-200">
                  {stats.lastVerified ? formatDate(stats.lastVerified) : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-4 border-b border-ink-800 pb-2">
                <dt className="text-mist-500">Cards priced</dt>
                <dd className="tnum text-mist-200">{stats.cards}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-mist-500">Commission taken</dt>
                <dd className="tnum text-mist-200">Nil</dd>
              </div>
            </dl>
            <Link
              href="/terms"
              className="mt-4 inline-block text-sm text-mist-400 underline underline-offset-4 transition hover:text-mist-50"
            >
              Terms &amp; data policy
            </Link>
          </div>
        </div>

        <p className="mt-10 border-t border-ink-800 pt-6 text-xs leading-relaxed text-mist-500">
          This is an informational comparison, not financial advice. Fees, exchange rates and
          product terms change — check the provider&apos;s current terms before applying. ForexMatch
          does not issue cards, process applications, or ask for KYC documents, and takes no
          commission from any provider.
        </p>
      </div>
    </footer>
  );
}
