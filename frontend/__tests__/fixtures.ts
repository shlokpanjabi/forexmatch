import type { CardEvaluation, Recommendation, StreamEvent, ToolEvent } from "@/lib/types";

export const toolEvent = (over: Partial<ToolEvent> = {}): ToolEvent => ({
  id: "evt-1",
  tool_name: "compare_cards",
  status: "success",
  input_summary: "all eligible cards",
  output_summary: "winner: Multi-Currency Forex Card (82%), 13 compared",
  error_message: null,
  duration_ms: 9,
  started_at: "2026-09-08T10:00:00Z",
  completed_at: "2026-09-08T10:00:01Z",
  ...over,
});

export const evaluation = (over: Partial<CardEvaluation> = {}): CardEvaluation => ({
  card: {
    id: "card-1",
    slug: "axis-multi-currency-forex-card",
    provider: "Axis Bank",
    card_name: "Multi-Currency Forex Card",
    card_type: "multi_currency_forex",
    network: "visa",
    description: null,
    supported_currencies: ["GBP", "USD"],
    currency_support_verified: true,
    freshness: "fresh",
    last_verified_at: "2026-09-08T00:00:00Z",
  },
  match_score: 82,
  estimated_cost: {
    total_inr: "7046.75",
    total_spend_currency: "54.86",
    spend_currency: "GBP",
    duration_months: 24,
    total_is_lower_bound: false,
    components: [
      {
        fee_type: "issuance",
        label: "Card issuance",
        amount_inr: "300.00",
        basis: "one-off issuance fee",
        is_imputed: false,
        imputation_note: null,
      },
      {
        fee_type: "atm_withdrawal",
        label: "ATM withdrawals",
        amount_inr: "4346.75",
        basis: "24 withdrawals over 24 months",
        is_imputed: true,
        imputation_note:
          "Provider does not publish this charge; the highest figure among the compared cards was used instead of assuming it is free.",
      },
    ],
    unknown_components: [],
    imputed_components: ["atm_withdrawal"],
    assumptions: ["Assumed 1 reload per month (24 in total)."],
    fx_rate_used: "GBP/INR 128.4500 (frankfurter)",
    fx_retrieved_at: "2026-09-08T10:00:00Z",
  },
  scores: [
    { component: "cost", score: 82, weight: 0.4, explanation: "Estimated ₹7,047 over the period." },
  ],
  key_reasons: ["Holds GBP directly, so purchases are not converted."],
  downsides: ["No rewards documented."],
  best_for: ["Spending in GBP"],
  application_url: "https://www.axis.bank.in/forex/forex-card/multi-currency-forex-card",
  sources: [
    {
      url: "https://www.axis.bank.in/fees.pdf",
      domain: "axis.bank.in",
      title: "Fees and Charges — Multi-Currency Forex Card",
      source_type: "official_fee_schedule",
      is_official: true,
      last_verified_at: "2026-09-08T00:00:00Z",
    },
  ],
  last_verified: "2026-09-08T00:00:00Z",
  ...over,
});

export const recommendation = (over: Partial<Recommendation> = {}): Recommendation => ({
  recommended_card: evaluation(),
  alternatives: [],
  comparison: [evaluation()],
  excluded: [{ card_name: "ForexPlus Card (Corporate)", provider: "HDFC Bank", reason: "No application route is published." }],
  assumptions: ["Assumed 1 reload per month (24 in total)."],
  confidence: "medium",
  confidence_reasons: ["Only one official source backs the leading card."],
  tied_with_recommended: [],
  weights_used: { cost: 0.4, atm: 0.15 },
  weights_were_customised: false,
  spend_currency: "GBP",
  duration_months: 24,
  sources: [],
  generated_at: "2026-09-08T10:00:00Z",
  disclaimer:
    "This is an informational comparison, not financial advice. Card fees and terms can change.",
  ...over,
});

/** Builds an SSE body from stream events, exactly as the backend frames them. */
export function sseBody(events: StreamEvent[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      }
      controller.close();
    },
  });
}
