import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ForexMatch — find the right forex card",
  description:
    "An agent that researches and compares forex cards for Indian students, using published provider data and today's exchange rates.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh bg-white text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
        {children}
      </body>
    </html>
  );
}
