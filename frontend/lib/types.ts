// Mirrors backend/app/schemas/serializers.py. Keep the two in step.

export type Confidence = "high" | "medium" | "low";
export type Freshness = "fresh" | "recent" | "aging" | "stale" | "unknown";
export type ToolStatus = "started" | "success" | "error";

export interface Source {
  url: string;
  domain: string;
  title: string | null;
  source_type: string;
  is_official: boolean;
  last_verified_at: string;
}

export interface CardSummary {
  id: string;
  slug: string;
  provider: string;
  card_name: string;
  card_type: string;
  network: string;
  description: string | null;
  supported_currencies: string[];
  /** False when we could not verify which currencies the card holds. */
  currency_support_verified: boolean;
  freshness: Freshness;
  last_verified_at: string | null;
}

export interface CostComponent {
  fee_type: string;
  label: string;
  amount_inr: string;
  basis: string;
  /** True when the provider publishes nothing and a worst-case figure was substituted. */
  is_imputed: boolean;
  imputation_note: string | null;
}

export interface CostBreakdown {
  total_inr: string;
  total_spend_currency: string | null;
  spend_currency: string | null;
  duration_months: number;
  total_is_lower_bound: boolean;
  components: CostComponent[];
  unknown_components: string[];
  imputed_components: string[];
  assumptions: string[];
  fx_rate_used: string | null;
  fx_retrieved_at: string | null;
}

export interface ComponentScore {
  component: string;
  score: number;
  weight: number;
  explanation: string;
}

export interface CardEvaluation {
  card: CardSummary;
  match_score: number;
  estimated_cost: CostBreakdown;
  scores: ComponentScore[];
  key_reasons: string[];
  downsides: string[];
  best_for: string[];
  application_url: string | null;
  sources: Source[];
  last_verified: string | null;
}

export interface ExcludedCard {
  card_name: string;
  provider: string;
  reason: string;
}

export interface Recommendation {
  recommended_card: CardEvaluation | null;
  alternatives: CardEvaluation[];
  comparison: CardEvaluation[];
  excluded: ExcludedCard[];
  assumptions: string[];
  confidence: Confidence;
  confidence_reasons: string[];
  tied_with_recommended: string[];
  weights_used: Record<string, number>;
  weights_were_customised: boolean;
  spend_currency: string | null;
  duration_months: number;
  sources: Source[];
  generated_at: string;
  disclaimer: string;
}

export interface SpendEstimate {
  min_amount: string | null;
  max_amount: string | null;
  currency: string | null;
  confidence: string;
}

export interface Profile {
  destination_country: string | null;
  destination_currencies: string[];
  trip_duration_months: number | null;
  monthly_spend: SpendEstimate;
  atm_usage: string;
  atm_withdrawals_per_month: number | null;
  expected_reload_frequency: number | null;
  needs_multiple_currencies: boolean | null;
  student_status: boolean | null;
  priorities: Record<string, number>;
  priorities_customised: boolean;
}

export interface ToolEvent {
  id: string;
  tool_name: string;
  status: ToolStatus;
  input_summary: string | null;
  output_summary: string | null;
  error_message: string | null;
  duration_ms: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
}

export type StreamEvent =
  | { type: "session"; session_id: string }
  | { type: "tool_event"; event: ToolEvent }
  | { type: "text"; text: string }
  | { type: "profile"; profile: Profile }
  | { type: "recommendation"; recommendation: Recommendation }
  | { type: "done"; message: string }
  | { type: "error"; error: { code: string; message: string } };

export interface ApiError {
  error: { code: string; message: string; [key: string]: unknown };
}
