/**
 * Abstract artwork for a card.
 *
 * Deliberately diagrammatic rather than a mock-up of the real product: these
 * are our illustrations, not the provider's, and nobody should mistake one for
 * a photograph of the card they are about to apply for. The only literal
 * information shown is data we actually hold — the currencies it carries.
 *
 * Everything visual derives from a hash of the slug, so a given card always
 * looks the same and no two neighbours look alike.
 */

function hash(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

export function CardArt({
  slug,
  currencies = [],
  className = "",
  compact = false,
}: {
  slug: string;
  currencies?: string[];
  className?: string;
  compact?: boolean;
}) {
  const h = hash(slug);
  // Hues stay within a warm arc so the catalogue reads as one family.
  const hue = 340 + (h % 50); // deep pink → red → warm orange
  const hue2 = (hue + 18 + (h % 14)) % 360;
  const tilt = ((h >> 3) % 10) - 5;
  const id = `art-${slug.replace(/[^a-z0-9]/gi, "")}`;

  return (
    <svg
      viewBox="0 0 320 200"
      role="img"
      aria-label={`Stylised artwork representing the ${slug.replace(/-/g, " ")}`}
      className={className}
    >
      <defs>
        <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={`hsl(${hue} 66% 34%)`} />
          <stop offset="55%" stopColor={`hsl(${hue2} 58% 20%)`} />
          <stop offset="100%" stopColor="hsl(345 38% 11%)" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="18%" cy="12%" r="70%">
          <stop offset="0%" stopColor={`hsl(${hue} 88% 62%)`} stopOpacity="0.62" />
          <stop offset="100%" stopColor="transparent" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-chip`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(42 70% 72%)" />
          <stop offset="100%" stopColor="hsl(32 55% 46%)" />
        </linearGradient>
        <clipPath id={`${id}-clip`}>
          <rect x="8" y="8" width="304" height="184" rx="18" />
        </clipPath>
      </defs>

      <g transform={`rotate(${tilt / 3} 160 100)`}>
        <rect x="8" y="8" width="304" height="184" rx="18" fill={`url(#${id}-bg)`} />

        <g clipPath={`url(#${id}-clip)`}>
          <rect x="8" y="8" width="304" height="184" fill={`url(#${id}-glow)`} />

          {/* Contour lines — a guilloche nod, kept faint. */}
          {Array.from({ length: 7 }, (_, i) => (
            <path
              key={i}
              d={`M -20 ${40 + i * 26 + (h % 11)} C 80 ${10 + i * 24}, 200 ${
                90 + i * 20
              }, 340 ${30 + i * 25}`}
              fill="none"
              stroke="white"
              strokeOpacity={0.07 + (i % 3) * 0.02}
              strokeWidth="1"
            />
          ))}

          {/* Payment-network suggestion: two overlapping discs, unbranded. */}
          <g opacity="0.16" transform="translate(238 132)">
            <circle cx="0" cy="0" r="26" fill="white" />
            <circle cx="30" cy="0" r="26" fill="white" />
          </g>
        </g>

        {/* Chip */}
        <g transform="translate(34 58)">
          <rect width="42" height="32" rx="6" fill={`url(#${id}-chip)`} />
          <g stroke="hsl(32 40% 30%)" strokeWidth="1.1" opacity="0.65">
            <path d="M0 11 h13 M0 21 h13 M29 11 h13 M29 21 h13" />
            <rect x="13" y="6" width="16" height="20" rx="3" fill="none" />
          </g>
        </g>

        {!compact && currencies.length > 0 && (
          <g
            fontFamily="var(--font-jetbrains-mono, monospace)"
            fontSize="10"
            letterSpacing="1.6"
            fill="white"
            fillOpacity="0.72"
          >
            {currencies.slice(0, 6).map((code, i) => (
              <text key={code} x={34 + (i % 3) * 52} y={132 + Math.floor(i / 3) * 18}>
                {code}
              </text>
            ))}
            {currencies.length > 6 && (
              <text x={34} y={168} fillOpacity="0.4">
                +{currencies.length - 6} more
              </text>
            )}
          </g>
        )}

        <rect
          x="8"
          y="8"
          width="304"
          height="184"
          rx="18"
          fill="none"
          stroke="white"
          strokeOpacity="0.18"
        />
      </g>
    </svg>
  );
}
