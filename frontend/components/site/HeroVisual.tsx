import { CardArt } from "@/components/ui/CardArt";

/**
 * The hero composition.
 *
 * Three cards suspended in an ember glow, each drifting slightly out of phase
 * so the stack reads as floating rather than pasted down. Built from the same
 * artwork the catalogue uses, so the front page is made of the product rather
 * than of stock imagery — and there is no photograph anyone could mistake for a
 * real product shot.
 *
 * Entirely decorative: hidden from assistive technology, and the drift stops
 * under prefers-reduced-motion.
 */

const CARDS = [
  {
    slug: "axis-multi-currency-forex-card",
    currencies: ["GBP", "EUR", "USD", "AUD", "SGD", "CHF"],
    className: "left-0 top-14 w-[58%] -rotate-[14deg]",
    delay: "0s",
    z: "z-10",
    opacity: "opacity-70",
  },
  {
    slug: "wsfx-globalpay-smart-currency-card",
    currencies: ["USD", "GBP", "EUR", "CAD", "AED", "JPY"],
    className: "right-0 top-0 w-[60%] rotate-[10deg]",
    delay: "1.4s",
    z: "z-20",
    opacity: "opacity-85",
  },
  {
    slug: "bookmyforex-multi-currency-forex-card",
    currencies: ["GBP", "USD", "EUR", "SGD"],
    className: "left-[16%] bottom-0 w-[66%] rotate-[3deg]",
    delay: "2.6s",
    z: "z-30",
    opacity: "opacity-100",
  },
];

export function HeroVisual() {
  return (
    <div aria-hidden className="pointer-events-none relative mx-auto aspect-[5/4] w-full max-w-lg">
      {/* Ember behind the stack */}
      <div
        className="sheen absolute inset-0 blur-2xl"
        style={{
          background:
            "radial-gradient(45% 45% at 55% 45%, rgba(226,61,46,0.5) 0%, rgba(142,26,19,0.22) 45%, transparent 72%)",
        }}
      />

      {CARDS.map((card) => (
        <div
          key={card.slug}
          className={`drift absolute ${card.className} ${card.z} ${card.opacity}`}
          style={{ animationDelay: card.delay }}
        >
          <div className="overflow-hidden rounded-2xl shadow-[0_28px_70px_-18px_rgba(0,0,0,0.85)] ring-1 ring-white/10">
            <CardArt slug={card.slug} currencies={card.currencies} className="block w-full" />
          </div>
        </div>
      ))}

      {/* Floor shadow, so the stack sits in the page rather than on it */}
      <div
        className="absolute inset-x-8 bottom-2 h-10 rounded-[50%] blur-2xl"
        style={{ background: "rgba(0,0,0,0.65)" }}
      />
    </div>
  );
}
