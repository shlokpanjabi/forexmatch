import { API_BASE } from "./api";
import type { CardDetail, CardSummary } from "./types";

export interface CatalogueStats {
  cards: number;
  providers: number;
  currencies: number;
  /** Most recent verification across the whole catalogue, ISO 8601. */
  lastVerified: string | null;
  /** How many cards are still inside the 30-day "recent" window. */
  freshCards: number;
  /** True when these came from the API rather than the fallback. */
  live: boolean;
}

/** Figures quoted on the marketing pages, kept honest by reading the real catalogue. */
const FALLBACK: CatalogueStats = {
  cards: 16,
  providers: 7,
  currencies: 20,
  lastVerified: null,
  freshCards: 0,
  live: false,
};

export async function getCatalogueStats(): Promise<CatalogueStats> {
  try {
    const response = await fetch(`${API_BASE}/api/cards`, {
      next: { revalidate: 3600 },
    });
    if (!response.ok) return FALLBACK;
    const body = (await response.json()) as { count: number; cards: CardSummary[] };
    const providers = new Set(body.cards.map((c) => c.provider));
    const currencies = new Set(body.cards.flatMap((c) => c.supported_currencies));
    const verified = body.cards
      .map((c) => c.last_verified_at)
      .filter((d): d is string => Boolean(d))
      .sort();

    return {
      cards: body.count,
      providers: providers.size,
      currencies: currencies.size,
      lastVerified: verified.at(-1) ?? null,
      freshCards: body.cards.filter((c) => c.freshness === "fresh" || c.freshness === "recent")
        .length,
      live: true,
    };
  } catch {
    // The landing page must render whether or not the API is reachable.
    return FALLBACK;
  }
}

export async function getCards(currency?: string): Promise<CardSummary[]> {
  try {
    const url = new URL(`${API_BASE}/api/cards`);
    if (currency) url.searchParams.set("currency", currency);
    const response = await fetch(url.toString(), { next: { revalidate: 3600 } });
    if (!response.ok) return [];
    const body = (await response.json()) as { cards: CardSummary[] };
    return body.cards;
  } catch {
    return [];
  }
}

export async function getCard(slug: string): Promise<CardDetail | null> {
  try {
    const response = await fetch(`${API_BASE}/api/cards/${encodeURIComponent(slug)}`, {
      next: { revalidate: 3600 },
    });
    if (!response.ok) return null;
    return (await response.json()) as CardDetail;
  } catch {
    return null;
  }
}
