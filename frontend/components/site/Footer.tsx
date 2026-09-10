import Link from "next/link";

export function Footer() {
  return (
    <footer className="relative z-10 mt-24 border-t border-ink-800">
      <div className="mx-auto max-w-6xl px-5 py-10">
        <div className="grid gap-8 sm:grid-cols-3">
          <div>
            <p className="display text-base">ForexMatch</p>
            <p className="mt-2 max-w-xs text-sm text-mist-400">
              Every figure comes from a provider&apos;s own published material, stored with the
              document it came from and the date it was checked.
            </p>
          </div>
          <div>
            <p className="label">Explore</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link href="/cards" className="text-mist-200 transition hover:text-ember-400">
                  All cards
                </Link>
              </li>
              <li>
                <Link href="/pick" className="text-mist-200 transition hover:text-ember-400">
                  Find my card
                </Link>
              </li>
              <li>
                <Link href="/chat" className="text-mist-200 transition hover:text-ember-400">
                  Ask the agent
                </Link>
              </li>
              <li>
                <Link href="/about" className="text-mist-200 transition hover:text-ember-400">
                  How it works
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="label">Source</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <a
                  href="https://github.com/shlokpanjabi/forexmatch"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-mist-200 transition hover:text-ember-400"
                >
                  GitHub
                </a>
              </li>
            </ul>
          </div>
        </div>

        <p className="mt-10 border-t border-ink-800 pt-6 text-xs leading-relaxed text-mist-500">
          This is an informational comparison, not financial advice. Fees, exchange rates and
          product terms change — check the provider&apos;s current terms before applying. ForexMatch
          does not issue cards, process applications, or ask for KYC documents. We take no
          commission from any provider.
        </p>
      </div>
    </footer>
  );
}
