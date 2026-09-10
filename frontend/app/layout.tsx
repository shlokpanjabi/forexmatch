import type { Metadata } from "next";
import { Instrument_Serif, Inter, JetBrains_Mono } from "next/font/google";

import "./globals.css";

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ForexMatch — the honest forex card comparison",
  description:
    "Tell us where you're going and how you'll spend. An agent researches the cards, prices them against your actual usage, and shows its working. No commissions, no paid placements.",
  openGraph: {
    title: "ForexMatch — the honest forex card comparison",
    description:
      "An agent that researches forex cards for Indian students and prices them against your real spending.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${instrumentSerif.variable} ${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="grain min-h-dvh bg-ink-950 text-mist-50">{children}</body>
    </html>
  );
}
