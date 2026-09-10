import Link from "next/link";

import { LinkButton } from "@/components/ui/primitives";

const LINKS = [
  { href: "/cards", label: "All cards" },
  { href: "/about", label: "How it works" },
];

export function Nav() {
  return (
    <header className="relative z-20 border-b border-ink-800/80">
      <nav className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-4">
        <Link href="/" className="group flex items-center gap-2">
          <span
            aria-hidden
            className="block size-2.5 rotate-45 bg-ember-500 transition group-hover:bg-ember-400"
          />
          <span className="display text-lg tracking-tight">ForexMatch</span>
        </Link>

        <div className="ml-auto flex items-center gap-1 sm:gap-4">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded px-2 py-1 font-mono text-[11px] uppercase tracking-widest text-mist-400 transition hover:text-mist-50"
            >
              {link.label}
            </Link>
          ))}
          <LinkButton href="/pick" size="md" className="ml-1">
            Find my card
          </LinkButton>
        </div>
      </nav>
    </header>
  );
}
