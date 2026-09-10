"""Component scoring and weighted ranking (BUILD.md sections 22–28).

Every score is a feature rule over structured card data, and every score carries
the sentence that explains it. Nothing here consults a model: if a number cannot
be explained from the card facts, it is not produced.
"""

from __future__ import annotations

from decimal import Decimal

from app.enums import BenefitType, FeeType, LimitType, ScoreComponent
from app.fx.models import FXRateTable
from app.recommendation.calculator import UsageProfile
from app.recommendation.models import CardFacts, ComponentScore, CostBreakdown
from app.schemas.profile import PriorityWeights, UserProfile

#: Final scores closer than this are treated as a tie (BUILD.md section 60).
TIE_THRESHOLD = 2.0

#: Where no relevant data exists at all, we sit at the midpoint rather than
#: rewarding or punishing a card for our own missing information.
NEUTRAL = 50.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


# --- Cost --------------------------------------------------------------------


def score_cost(
    card_id: str, costs: dict[str, CostBreakdown]
) -> tuple[float, str]:
    """Cheapest card scores 100, dearest 0 (BUILD.md section 23).

    Identical costs all score 100 — there is nothing to separate them, and the
    normalisation would otherwise divide by zero.
    """
    totals = {key: breakdown.total_inr for key, breakdown in costs.items()}
    if not totals:
        return NEUTRAL, "No cost data available."

    min_cost = min(totals.values())
    max_cost = max(totals.values())
    own = totals[card_id]

    if max_cost == min_cost:
        return 100.0, f"All compared cards cost about ₹{own:,.0f} for this usage."

    score = 100.0 * float(max_cost - own) / float(max_cost - min_cost)
    breakdown = costs[card_id]
    suffix = ""
    if breakdown.imputed_components:
        suffix = " (includes a substituted figure for a charge this provider does not publish)"
    elif breakdown.total_is_lower_bound:
        suffix = " (a lower bound — some charges are unpublished across every card here)"

    # Phrase this so it reads correctly whether the card leads on cost or not —
    # "₹7,047 more than the cheapest" must never be presented as a selling point.
    above_cheapest = own - min_cost
    below_dearest = max_cost - own
    if above_cheapest == 0:
        detail = "the cheapest option in this comparison"
    elif below_dearest == 0:
        detail = f"the most expensive here, ₹{above_cheapest:,.0f} above the cheapest"
    else:
        detail = (
            f"₹{above_cheapest:,.0f} above the cheapest option "
            f"and ₹{below_dearest:,.0f} below the most expensive"
        )
    return _clamp(score), f"Estimated ₹{own:,.0f} over the period — {detail}{suffix}."


# --- ATM ---------------------------------------------------------------------


def score_atm(card: CardFacts, usage: UsageProfile, fx: FXRateTable) -> tuple[float, str]:
    """Cash economics, weighted by how much cash the user actually expects to use.

    When someone withdraws nothing, every card scores alike: ATM terms genuinely
    do not separate them, and pretending otherwise would distort the ranking
    (BUILD.md section 24).
    """
    if usage.atm_withdrawals_total == 0:
        return 100.0, "You do not expect to withdraw cash, so ATM charges do not separate these cards."

    fee = card.fee(FeeType.ATM_WITHDRAWAL, currency=usage.spend_currency)
    if fee is None or not fee.is_known:
        return (
            25.0,
            "This provider does not publish an overseas ATM charge, so cash use here is unpredictable.",
        )

    if fee.is_waived:
        base, detail = 100.0, "No overseas ATM withdrawal fee is charged"
    else:
        flat = fee.effective_amount
        currency = fee.currency or "INR"
        per_withdrawal_inr = None
        if flat is not None:
            per_withdrawal_inr = flat if currency.upper() == "INR" else fx.convert(flat, currency, "INR")
        if per_withdrawal_inr is None and fee.effective_percentage is not None:
            if usage.average_atm_withdrawal is not None:
                pct_amount = usage.average_atm_withdrawal * fee.effective_percentage / Decimal(100)
                per_withdrawal_inr = fx.convert(pct_amount, usage.spend_currency, "INR")
        if per_withdrawal_inr is None:
            return 30.0, "An ATM charge is published but could not be converted to rupees."

        # ₹100 or less per withdrawal is excellent; ₹600+ is poor.
        value = float(per_withdrawal_inr)
        base = _clamp(100.0 - (value - 100.0) / 5.0)
        detail = f"About ₹{value:,.0f} per withdrawal"

    notes = [detail]

    daily_limit = card.limit(LimitType.DAILY_ATM)
    if daily_limit is not None and daily_limit.amount is not None:
        if usage.average_atm_withdrawal is not None and daily_limit.currency:
            limit_in_spend = fx.convert(daily_limit.amount, daily_limit.currency, usage.spend_currency)
            if limit_in_spend is not None and limit_in_spend < usage.average_atm_withdrawal:
                base -= 15.0
                notes.append(
                    f"the daily ATM cap of {daily_limit.currency} {daily_limit.amount:,.0f} "
                    "is below your typical withdrawal"
                )

    if usage.atm_withdrawals_total >= 8 * max(usage.duration_months, 1) / 12:
        notes.append(f"you expect around {usage.atm_withdrawals_total} withdrawals in total")

    return _clamp(base), "; ".join(notes) + "."


# --- Currency ----------------------------------------------------------------


def score_currency(card: CardFacts, profile: UserProfile, usage: UsageProfile) -> tuple[float, str]:
    """Holding the destination currency directly beats converting every purchase
    (BUILD.md section 25)."""
    target = usage.spend_currency
    supported_count = len(card.supported_currency_codes)

    if not card.currencies:
        return (
            35.0,
            "This provider's supported-currency list could not be verified, so "
            f"we cannot confirm it holds {target}.",
        )

    if card.has_direct_wallet(target):
        score = 95.0
        detail = f"Holds {target} directly, so purchases are not converted"
    elif card.supports_currency(target):
        score = 60.0
        detail = f"Supports {target}, but not as a dedicated wallet"
    else:
        cross = card.fee(FeeType.CROSS_CURRENCY)
        markup = cross.effective_percentage if cross is not None else None
        if markup is not None:
            # Converting every purchase is a real drawback, but converting at no
            # markup is far better than converting at 3.5%. Scoring both the same
            # would rank a zero-markup card as though it charged full spread.
            score = _clamp(70.0 - float(markup) * 10.0)
            if markup == 0:
                # No penalty here: every converting card has an undisclosed
                # spread, so it does not separate them. A published 0% fee is
                # genuinely better than a published 3.5% one. What the spread
                # does affect is the *cost* estimate, handled in the calculator.
                detail = (
                    f"Does not hold {target}. The provider charges no cross-currency fee, but "
                    "every purchase is still converted at their own rate and the spread is not "
                    "published"
                )
            else:
                detail = f"Does not hold {target}; every purchase is converted at {markup}%"
        else:
            score = 20.0
            detail = f"Does not hold {target}, and the conversion charge is not published"

    if profile.needs_multiple_currencies and supported_count >= 10:
        score = min(100.0, score + 5.0)
        detail += f"; covers {supported_count} currencies for multi-country travel"
    elif profile.needs_multiple_currencies and supported_count <= 1:
        score -= 20.0
        detail += "; single-currency card, which does not fit multi-country travel"
    elif supported_count > 1:
        detail += f"; {supported_count} currencies supported"

    return _clamp(score), detail + "."


# --- Feature-rule components -------------------------------------------------

#: (benefit, points, phrase) — additive rules, so every score decomposes into
#: the documented features that produced it.
CONVENIENCE_RULES: tuple[tuple[BenefitType, float, str], ...] = (
    (BenefitType.ONLINE_APPLICATION, 15.0, "can be applied for online"),
    (BenefitType.ONLINE_RELOAD, 15.0, "reloads online"),
    (BenefitType.ONLINE_MANAGEMENT, 10.0, "online card management"),
    (BenefitType.EMERGENCY_REPLACEMENT, 5.0, "emergency replacement"),
)

REWARDS_RULES: tuple[tuple[BenefitType, float, str], ...] = (
    (BenefitType.CASHBACK, 20.0, "cashback"),
    (BenefitType.DISCOUNT, 12.0, "merchant discounts"),
    (BenefitType.LOUNGE_ACCESS, 15.0, "airport lounge access"),
    (BenefitType.INSURANCE, 10.0, "insurance cover"),
    (BenefitType.TRAVEL, 8.0, "travel benefits"),
)

SECURITY_RULES: tuple[tuple[BenefitType, float, str], ...] = (
    (BenefitType.FRAUD_PROTECTION, 15.0, "fraud protection"),
    (BenefitType.CARD_CONTROLS, 12.0, "card controls"),
    (BenefitType.TRANSACTION_ALERTS, 10.0, "transaction alerts"),
    (BenefitType.EMERGENCY_ASSISTANCE, 8.0, "emergency assistance"),
    (BenefitType.EMERGENCY_REPLACEMENT, 8.0, "emergency replacement"),
)


def _score_from_rules(
    card: CardFacts,
    rules: tuple[tuple[BenefitType, float, str], ...],
    *,
    label: str,
    baseline: float = NEUTRAL,
) -> tuple[float, str]:
    matched = [(points, phrase) for benefit, points, phrase in rules if card.has_benefit(benefit)]
    if not matched:
        return (
            baseline - 15.0,
            f"No {label} documented in the provider's published material.",
        )
    score = baseline + sum(points for points, _ in matched)
    phrases = ", ".join(phrase for _, phrase in matched)
    return _clamp(score), f"Documented: {phrases}."


def score_convenience(card: CardFacts, profile: UserProfile) -> tuple[float, str]:
    score, explanation = _score_from_rules(card, CONVENIENCE_RULES, label="convenience features")
    if profile.student_status:
        student_rule = any(
            e.criterion.value == "student_only" for e in card.eligibility
        ) or "student" in card.card_name.lower()
        if student_rule:
            score = _clamp(score + 8.0)
            explanation = explanation.rstrip(".") + "; positioned as a student product."
    if card.application_url is None:
        score = _clamp(score - 20.0)
        explanation = explanation.rstrip(".") + "; no published application route."
    return score, explanation


def score_rewards(card: CardFacts) -> tuple[float, str]:
    return _score_from_rules(card, REWARDS_RULES, label="rewards or travel benefits")


def score_security(card: CardFacts) -> tuple[float, str]:
    return _score_from_rules(card, SECURITY_RULES, label="security features")


# --- Aggregation -------------------------------------------------------------


def score_card(
    card: CardFacts,
    *,
    profile: UserProfile,
    usage: UsageProfile,
    costs: dict[str, CostBreakdown],
    fx: FXRateTable,
    weights: PriorityWeights,
) -> tuple[tuple[ComponentScore, ...], float]:
    """Score one card across all six components and combine by weight."""
    normalised = weights.normalised()
    weight_map = normalised.as_dict()

    raw: dict[ScoreComponent, tuple[float, str]] = {
        ScoreComponent.COST: score_cost(str(card.id), costs),
        ScoreComponent.ATM: score_atm(card, usage, fx),
        ScoreComponent.CURRENCY_SUPPORT: score_currency(card, profile, usage),
        ScoreComponent.CONVENIENCE: score_convenience(card, profile),
        ScoreComponent.REWARDS: score_rewards(card),
        ScoreComponent.SECURITY: score_security(card),
    }

    components = tuple(
        ComponentScore(
            component=component,
            score=round(value, 2),
            weight=round(weight_map[component], 4),
            explanation=explanation,
        )
        for component, (value, explanation) in raw.items()
    )
    final = sum(component.weighted for component in components)
    return components, round(final, 2)
