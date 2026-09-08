"""Profile tools — what the agent has understood about the user."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from strands import tool

from app.agent.context import get_context, traced_tool
from app.enums import AtmUsage

_ATM_WORDS = {a.value for a in AtmUsage}


def _decimal(value: float | int | str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@tool
@traced_tool(
    describe_input=lambda: "current profile",
    describe_output=lambda r: (
        f"destination {r.get('destination_country') or '—'}, "
        f"spend {r.get('monthly_spend_display') or 'unknown'}"
    ),
)
async def get_user_profile() -> dict[str, Any]:
    """Return everything currently known about the user's trip and preferences.

    Call this before asking a question, so you do not ask for something the user
    has already told you.

    Returns the structured profile plus `missing_high_value_fields` — the only
    things still worth asking about.
    """
    ctx = get_context()
    profile = ctx.profile
    return {
        "destination_country": profile.destination_country,
        "destination_currencies": profile.destination_currencies,
        "trip_type": profile.trip_type.value if profile.trip_type else None,
        "trip_duration_months": profile.trip_duration_months,
        "monthly_spend_min": str(profile.monthly_spend.min_amount) if profile.monthly_spend.min_amount else None,
        "monthly_spend_max": str(profile.monthly_spend.max_amount) if profile.monthly_spend.max_amount else None,
        "monthly_spend_currency": profile.monthly_spend.currency,
        "monthly_spend_display": profile.monthly_spend.describe(),
        "monthly_spend_confidence": profile.monthly_spend.confidence.value,
        "atm_usage": profile.atm_usage.value,
        "atm_withdrawals_per_month": profile.atm_withdrawals_per_month,
        "expected_reload_frequency": profile.expected_reload_frequency,
        "needs_multiple_currencies": profile.needs_multiple_currencies,
        "student_status": profile.student_status,
        "currently_abroad": profile.currently_abroad,
        "priorities": profile.priorities.normalised().model_dump(),
        "priorities_customised": profile.priorities_customised,
        "ready_for_recommendation": profile.is_ready_for_recommendation,
        "missing_high_value_fields": profile.missing_high_value_fields(),
    }


@tool
@traced_tool(
    describe_input=lambda **kw: ", ".join(f"{k}={v}" for k, v in kw.items() if v is not None) or "no changes",
    describe_output=lambda r: f"updated: {', '.join(r.get('updated_fields', [])) or 'nothing'}",
)
async def update_user_profile(
    destination_country: str | None = None,
    destination_currency: str | None = None,
    trip_duration_months: int | None = None,
    monthly_spend_min: float | None = None,
    monthly_spend_max: float | None = None,
    monthly_spend_currency: str | None = None,
    spend_is_estimate: bool | None = None,
    atm_usage: str | None = None,
    atm_withdrawals_per_month: int | None = None,
    average_atm_withdrawal: float | None = None,
    reloads_per_month: int | None = None,
    needs_multiple_currencies: bool | None = None,
    student_status: bool | None = None,
    currently_abroad: bool | None = None,
    trip_type: str | None = None,
    priority_cost: float | None = None,
    priority_atm: float | None = None,
    priority_currency_support: float | None = None,
    priority_convenience: float | None = None,
    priority_rewards: float | None = None,
    priority_security: float | None = None,
) -> dict[str, Any]:
    """Record what the user has told you. Pass only the fields you actually learned.

    Spending may be a range: pass `monthly_spend_min` and `monthly_spend_max`
    when the user is unsure ("around £1,000–£1,200"). Never invent a precise
    figure the user did not give.

    `atm_usage` is one of: none, low, medium, high, unknown.
    `trip_type` is one of: study, tourism, business, other.

    The six `priority_*` values are relative weights. Pass them when the user
    says what matters ("I just want the cheapest" → priority_cost high, others
    low). They are normalised automatically, so any scale works.
    """
    ctx = get_context()
    updates: dict[str, Any] = {}

    if destination_country:
        updates["destination_country"] = destination_country
    if destination_currency:
        code = destination_currency.strip().upper()
        if len(code) == 3:
            existing = list(ctx.profile.destination_currencies)
            if code not in existing:
                existing.insert(0, code)
            updates["destination_currencies"] = existing
    if trip_duration_months is not None:
        updates["trip_duration_months"] = trip_duration_months
    if trip_type:
        updates["trip_type"] = trip_type

    spend: dict[str, Any] = {}
    if monthly_spend_min is not None:
        spend["min_amount"] = str(_decimal(monthly_spend_min))
    if monthly_spend_max is not None:
        spend["max_amount"] = str(_decimal(monthly_spend_max))
    if monthly_spend_currency:
        spend["currency"] = monthly_spend_currency.strip().upper()
    if spend_is_estimate is not None:
        spend["confidence"] = "estimated" if spend_is_estimate else "stated"
    if spend and "confidence" not in spend:
        # A single figure with no qualifier is still the user's own number.
        spend["confidence"] = "stated" if monthly_spend_min == monthly_spend_max else "estimated"
    if spend:
        updates["monthly_spend"] = spend

    if atm_usage and atm_usage.lower() in _ATM_WORDS:
        updates["atm_usage"] = atm_usage.lower()
    if atm_withdrawals_per_month is not None:
        updates["atm_withdrawals_per_month"] = atm_withdrawals_per_month
    if average_atm_withdrawal is not None:
        updates["average_atm_withdrawal"] = str(_decimal(average_atm_withdrawal))
    if reloads_per_month is not None:
        updates["expected_reload_frequency"] = reloads_per_month
    if needs_multiple_currencies is not None:
        updates["needs_multiple_currencies"] = needs_multiple_currencies
    if student_status is not None:
        updates["student_status"] = student_status
    if currently_abroad is not None:
        updates["currently_abroad"] = currently_abroad

    priorities = {
        "cost": priority_cost,
        "atm": priority_atm,
        "currency_support": priority_currency_support,
        "convenience": priority_convenience,
        "rewards": priority_rewards,
        "security": priority_security,
    }
    given = {k: v for k, v in priorities.items() if v is not None}
    if given:
        # A partial statement of priorities means the unmentioned ones are not
        # important, so start from zero rather than blending with our defaults.
        updates["priorities"] = {k: 0.0 for k in priorities} | given

    if not updates:
        return {"updated_fields": [], "profile_ready": ctx.profile.is_ready_for_recommendation}

    ctx.profile = ctx.profile.merged_with(updates)
    ctx.profile_dirty = True
    # The profile changed, so any earlier ranking no longer describes this user.
    ctx.recommendation = None

    return {
        "updated_fields": sorted(updates.keys()),
        "profile_ready": ctx.profile.is_ready_for_recommendation,
        "monthly_spend_display": ctx.profile.monthly_spend.describe(),
        "still_missing": ctx.profile.missing_high_value_fields(),
    }
