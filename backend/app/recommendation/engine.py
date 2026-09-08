"""The deterministic recommendation engine.

``recommend(profile, cards, fx)`` is a pure function: same inputs, same output,
no I/O, no model call. The LLM never picks the winner — it explains the winner
this function picked (BUILD.md sections 6, 17, 95, 96).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.enums import Confidence, FeeType, Freshness, ScoreComponent
from app.fx.models import FXRateTable
from app.recommendation.calculator import UsageProfile, calculate_costs, derive_usage
from app.recommendation.models import (
    CardEvaluation,
    CardFacts,
    CostBreakdown,
    ExcludedCard,
    RecommendationResult,
)
from app.recommendation.scorer import TIE_THRESHOLD, score_card
from app.schemas.profile import UserProfile

MAX_RESULTS = 3


# --- Hard filters ------------------------------------------------------------


def _exclusion_reason(card: CardFacts, profile: UserProfile, usage: UsageProfile) -> str | None:
    """Reasons a card cannot serve this user at all (BUILD.md section 29).

    Being merely worse is never grounds for exclusion — that is what scoring is
    for. Only genuine unsuitability belongs here.
    """
    if not card.is_active:
        return "This product is no longer offered."

    if card.application_url is None and card.affiliate_url is None:
        return "No application route is published for this card."

    target = usage.spend_currency
    if card.currencies and not card.supports_currency(target):
        cross = card.fee(FeeType.CROSS_CURRENCY)
        usable_by_conversion = cross is not None and cross.is_known
        if not usable_by_conversion:
            return (
                f"Does not support {target} and publishes no cross-currency terms, "
                "so it cannot be used at this destination."
            )

    if profile.student_status is False:
        for rule in card.eligibility:
            if rule.criterion.value == "student_only":
                return "Restricted to students, and you are not applying as one."

    return None


# --- Narrative ---------------------------------------------------------------


def _build_narrative(
    evaluation_scores: tuple, card: CardFacts, cost: CostBreakdown, usage: UsageProfile
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Reasons, downsides and 'best for' tags, all derived from the scores."""
    reasons: list[str] = []
    downsides: list[str] = []
    best_for: list[str] = []

    ranked = sorted(evaluation_scores, key=lambda s: s.weighted, reverse=True)
    for component in ranked:
        if component.score >= 75 and component.weight > 0:
            reasons.append(component.explanation)
        elif component.score <= 40:
            downsides.append(component.explanation)

    if cost.imputed_components:
        names = ", ".join(f.value.replace("_", " ") for f in cost.imputed_components)
        downsides.append(
            f"{card.provider} does not publish its {names} charge, so a worst-case figure was used."
        )
    if cost.unknown_components:
        downsides.append("Some charges are unpublished, so the estimate is a lower bound.")

    if card.freshness in (Freshness.STALE, Freshness.UNKNOWN):
        downsides.append("This card's data has not been verified recently.")

    if card.has_direct_wallet(usage.spend_currency):
        best_for.append(f"Spending in {usage.spend_currency}")
    if len(card.supported_currency_codes) >= 10:
        best_for.append("Multi-country travel")
    atm_fee = card.fee(FeeType.ATM_WITHDRAWAL)
    if atm_fee is not None and atm_fee.is_waived:
        best_for.append("Frequent cash withdrawals")
    if "student" in card.card_name.lower():
        best_for.append("Students")

    return tuple(reasons[:4]), tuple(dict.fromkeys(downsides))[:4], tuple(best_for[:3])


# --- Confidence --------------------------------------------------------------


def _assess_confidence(
    ranked: Sequence[CardEvaluation], costs: dict[str, CostBreakdown]
) -> tuple[Confidence, tuple[str, ...]]:
    """Confidence reflects data quality and how clearly the winner actually won
    (BUILD.md section 59)."""
    if not ranked:
        return Confidence.LOW, ("No card qualified for this profile.",)

    reasons: list[str] = []
    penalties = 0

    winner = ranked[0]
    winner_cost = costs[str(winner.card.id)]

    if winner_cost.unknown_components:
        penalties += 2
        reasons.append("Some charges on the leading card are unpublished.")
    elif winner_cost.imputed_components:
        penalties += 1
        reasons.append("A charge on the leading card was substituted rather than published.")

    freshness = winner.card.freshness
    if freshness in (Freshness.STALE, Freshness.UNKNOWN):
        penalties += 2
        reasons.append("The leading card's data has not been verified in the last 90 days.")
    elif freshness is Freshness.AGING:
        penalties += 1
        reasons.append("The leading card's data is between 30 and 90 days old.")

    official = len(winner.card.official_sources)
    if official == 0:
        penalties += 2
        reasons.append("No official provider source is attached to the leading card.")
    elif official == 1:
        penalties += 1
        reasons.append("Only one official source backs the leading card.")

    if len(ranked) >= 2:
        gap = ranked[0].final_score - ranked[1].final_score
        if gap < TIE_THRESHOLD:
            penalties += 2
            reasons.append(
                f"The top two cards are within {gap:.1f} points — they are effectively tied."
            )
        elif gap < 5:
            penalties += 1
            reasons.append("The top two cards are close for your usage.")
    else:
        penalties += 1
        reasons.append("Only one card qualified, so there is little to compare against.")

    if penalties == 0:
        return Confidence.HIGH, ("Backed by current official sources with a clear margin.",)
    if penalties <= 2:
        return Confidence.MEDIUM, tuple(reasons)
    return Confidence.LOW, tuple(reasons)


# --- Entry point -------------------------------------------------------------


def recommend(
    profile: UserProfile,
    cards: Sequence[CardFacts],
    fx: FXRateTable,
    *,
    max_results: int = MAX_RESULTS,
) -> RecommendationResult:
    """Rank cards for a user. Deterministic and side-effect free."""
    usage = derive_usage(profile)
    weights = profile.priorities.normalised()

    eligible: list[CardFacts] = []
    excluded: list[ExcludedCard] = []
    for card in cards:
        reason = _exclusion_reason(card, profile, usage)
        if reason:
            excluded.append(
                ExcludedCard(
                    card_id=card.id, provider=card.provider, card_name=card.card_name, reason=reason
                )
            )
        else:
            eligible.append(card)

    if not eligible:
        return RecommendationResult(
            excluded=tuple(excluded),
            assumptions=usage.assumptions,
            confidence=Confidence.LOW,
            confidence_reasons=("No card in the catalogue suits this destination and profile.",),
            weights_used={k.value: v for k, v in weights.as_dict().items()},
            weights_were_customised=profile.priorities_customised,
            spend_currency=usage.spend_currency,
            duration_months=usage.duration_months,
        )

    costs = calculate_costs(eligible, profile, fx, usage=usage)

    evaluations: list[CardEvaluation] = []
    for card in eligible:
        cost = costs[str(card.id)]
        scores, final = score_card(
            card, profile=profile, usage=usage, costs=costs, fx=fx, weights=weights
        )
        reasons, downsides, best_for = _build_narrative(scores, card, cost, usage)
        evaluations.append(
            CardEvaluation(
                card=card,
                cost=cost,
                scores=scores,
                final_score=final,
                key_reasons=reasons,
                downsides=downsides,
                best_for=best_for,
            )
        )

    # Stable ordering: score first, then cost, then name — so equal inputs always
    # produce an identical result.
    ranked = sorted(
        evaluations,
        key=lambda e: (-e.final_score, e.cost.total_inr, e.card.provider, e.card.card_name),
    )

    winner = ranked[0]
    tied = tuple(
        e.card.id
        for e in ranked[1:]
        if abs(e.final_score - winner.final_score) < TIE_THRESHOLD
    )

    confidence, confidence_reasons = _assess_confidence(ranked, costs)

    assumptions = list(usage.assumptions)
    assumptions.extend(a for a in winner.cost.assumptions if a not in assumptions)
    if not profile.priorities_customised:
        assumptions.append(
            "Ranked with our default priorities (cost weighted most heavily). "
            "Tell us what matters to you and we will re-rank."
        )

    return RecommendationResult(
        recommended=winner,
        alternatives=tuple(ranked[1:max_results]),
        comparison=tuple(ranked),
        excluded=tuple(excluded),
        assumptions=tuple(assumptions),
        confidence=confidence,
        confidence_reasons=confidence_reasons,
        tied_with_recommended=tied,
        weights_used={k.value: round(v, 4) for k, v in weights.as_dict().items()},
        weights_were_customised=profile.priorities_customised,
        spend_currency=usage.spend_currency,
        duration_months=usage.duration_months,
    )
