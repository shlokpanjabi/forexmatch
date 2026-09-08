"""Comparison tool — runs the deterministic ranking engine."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from strands import tool

from app.agent.context import get_context, traced_tool
from app.db.models import Card
from app.recommendation.service import RecommendationService
from app.schemas.serializers import recommendation_to_dict


@tool
@traced_tool(
    describe_input=lambda slugs=None: f"{len(slugs)} cards" if slugs else "all eligible cards",
    describe_output=lambda r: (
        f"winner: {r['recommended_card']['card']['card_name']} "
        f"({r['recommended_card']['match_score']}%), {len(r.get('comparison', []))} compared"
        if r.get("recommended_card")
        else "no qualifying card"
    ),
)
async def compare_cards(slugs: list[str] | None = None) -> dict[str, Any]:
    """Rank cards for this user and produce the recommendation.

    This is the only way a recommendation is made. The ranking is computed by a
    deterministic engine from the user's profile, the verified card data and
    today's reference rates — you must not choose a different winner, reorder
    the results, or adjust any score.

    Your job with the output is to explain it: why the top card fits *this*
    user, what the estimated cost is, what would change the answer, and what the
    alternatives are better at. If `confidence` is low or cards are tied, say so
    plainly rather than implying a clear victory.

    Omit `slugs` to compare everything eligible.
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

    card_ids = None
    if slugs:
        rows = (await ctx.db.execute(select(Card.id).where(Card.slug.in_(slugs)))).scalars().all()
        card_ids = list(rows) or None

    result = await RecommendationService(ctx.db).recommend_for_profile(ctx.profile, card_ids=card_ids)
    ctx.recommendation = result
    return recommendation_to_dict(result)
