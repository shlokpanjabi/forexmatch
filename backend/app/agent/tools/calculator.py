"""Cost tool — deterministic pricing for one card."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from strands import tool

from app.agent.context import get_context, traced_tool
from app.db.models import Card
from app.recommendation import calculator as cost_calculator
from app.recommendation.service import RecommendationService, load_cards, to_card_facts
from app.schemas.serializers import cost_to_dict


@tool
@traced_tool(
    describe_input=lambda slug: slug,
    describe_output=lambda r: (
        f"₹{r['estimated_cost']['total_inr']} over {r['estimated_cost']['duration_months']} months"
        if "estimated_cost" in r
        else "cost unavailable"
    ),
)
async def calculate_card_cost(slug: str) -> dict[str, Any]:
    """Price one card against the user's expected usage.

    The arithmetic happens in code, not in your head — report the numbers this
    returns and do not recompute or round them yourself.

    Check `is_imputed` on each component: where a provider publishes no figure,
    the highest charge among the compared cards is substituted so that missing
    data can never make a card look cheap. Say so when it applies.
    """
    ctx = get_context()
    if not ctx.profile.is_ready_for_recommendation:
        return {
            "error": {
                "code": "PROFILE_INCOMPLETE",
                "message": "Need at least a destination currency and a rough monthly spend first.",
                "missing": ctx.profile.missing_high_value_fields(),
            }
        }

    row = (await ctx.db.execute(select(Card).where(Card.slug == slug))).scalar_one_or_none()
    if row is None:
        return {"error": {"code": "CARD_NOT_FOUND", "message": f"No card with slug '{slug}'."}}

    card = to_card_facts(row)
    peers = await load_cards(ctx.db)
    fx = await RecommendationService(ctx.db).build_fx_table(ctx.profile)
    cost = cost_calculator.calculate_card_cost(card, ctx.profile, fx, peers=peers)

    return {
        "card": {"slug": card.slug, "provider": card.provider, "card_name": card.card_name},
        "estimated_cost": cost_to_dict(cost),
    }
