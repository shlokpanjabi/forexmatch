import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

/** Small uppercase monospace eyebrow. */
export function Label({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`label ${className}`}>{children}</span>;
}

/**
 * A surface. `raised` is for content that sits on the page; `sunken` is for
 * nested detail inside an already-raised card.
 */
export function Card({
  children,
  className = "",
  tone = "raised",
}: {
  children: ReactNode;
  className?: string;
  tone?: "raised" | "sunken" | "accent";
}) {
  const tones = {
    raised: "bg-ink-900 border-ink-800",
    sunken: "bg-ink-950 border-ink-800",
    accent: "bg-ink-900 border-ember-600/50",
  };
  return (
    <div className={`rounded-[--radius-card] border ${tones[tone]} ${className}`}>{children}</div>
  );
}

type ButtonProps = {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "lg";
} & ComponentProps<"button">;

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 font-medium transition disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ember-400";

const BUTTON_VARIANTS = {
  // The accent is rationed: one primary action per view. The deeper 600 is the
  // resting state because white on the brighter 500 only reaches 4.25:1.
  primary: "bg-ember-600 text-white hover:bg-ember-500 active:bg-ember-700",
  secondary: "border border-ink-700 text-mist-200 hover:border-ink-600 hover:text-mist-50",
  ghost: "text-mist-400 hover:text-mist-50",
};

const BUTTON_SIZES = {
  md: "h-10 px-4 text-sm rounded-lg",
  lg: "h-12 px-6 text-base rounded-xl",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`${BUTTON_BASE} ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function LinkButton({
  children,
  href,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: {
  children: ReactNode;
  href: string;
  variant?: keyof typeof BUTTON_VARIANTS;
  size?: keyof typeof BUTTON_SIZES;
  className?: string;
} & Omit<ComponentProps<typeof Link>, "href">) {
  return (
    <Link
      href={href}
      className={`${BUTTON_BASE} ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]} ${className}`}
      {...props}
    >
      {children}
    </Link>
  );
}

/** A number with its label, used for the stat rows. */
export function Stat({
  value,
  label,
  accent = false,
}: {
  value: string;
  label: string;
  accent?: boolean;
}) {
  return (
    <div>
      <p
        className={`display tnum text-3xl sm:text-4xl ${accent ? "text-ember-400" : "text-mist-50"}`}
      >
        {value}
      </p>
      <p className="label mt-1">{label}</p>
    </div>
  );
}

/** Status pill. Meanings are fixed app-wide, so the colour is derived here. */
export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "good" | "caution";
}) {
  const tones = {
    neutral: "bg-ink-800 text-mist-400 border-ink-700",
    accent: "bg-ember-600/15 text-ember-300 border-ember-600/40",
    good: "bg-jade-400/10 text-jade-400 border-jade-400/30",
    caution: "bg-amber-400/10 text-amber-400 border-amber-400/30",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-wider ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
