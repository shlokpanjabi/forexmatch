"""Catalogue tools — searching and inspecting verified card data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from strands import tool

from app.agent.context import get_context, traced_tool
from app.db.models import Card, CardCurrency
from app.recommendation.service import to_card_facts
from app.schemas.serializers import card_detail, card_summary


@tool
@traced_tool(
    describe_input=lambda **kw: ", ".join(f"{k}={v}" for k, v in kw.items() if v) or "all active cards",
    describe_output=lambda r: f"{r.get('count', 0)} cards found",
)
async def search_cards(
    destination_currency: str | None = None,
    provider: str | None = None,
    student_only: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """Find cards in the verified catalogue.

    Use this first, once you know where the user is going. Filtering by
    `destination_currency` (an ISO code such as GBP) returns cards that hold
    that currency *plus* cards whose currency list has not been verified — those
    are still candidates, and the comparison will flag the uncertainty.

    Returns summaries only. Use `get_card_details` for fees.
    """
    ctx = get_context()
    stmt = select(Card).where(Card.is_active.is_(True))

    if provider:
        stmt = stmt.where(Card.provider.ilike(f"%{provider}%"))

    if destination_currency:
        code = destination_currency.strip().upper()
        supports = select(CardCurrency.card_id).where(
            CardCurrency.currency_code == code, CardCurrency.supported.is_(True)
        )
        has_any_currency_data = select(CardCurrency.card_id)
        # Keep cards with no verified currency list — excluding them would hide
        # products we simply have not confirmed yet.
        stmt = stmt.where(Card.id.in_(supports) | Card.id.notin_(has_any_currency_data))

    stmt = stmt.order_by(Card.provider, Card.card_name).limit(max(1, min(limit, 50)))
    rows = (await ctx.db.execute(stmt)).scalars().unique().all()
    cards = [to_card_facts(row) for row in rows]

    if student_only:
        cards = [
            c
            for c in cards
            if "student" in c.card_name.lower()
            or any(e.criterion.value == "student_only" for e in c.eligibility)
        ] or cards

    return {
        "count": len(cards),
        "filters": {
            "destination_currency": destination_currency,
            "provider": provider,
            "student_only": student_only,
        },
        "cards": [card_summary(c) for c in cards],
    }


@tool
@traced_tool(
    describe_input=lambda slug: slug,
    describe_output=lambda r: (
        f"{r.get('card_name', 'unknown')}: {len(r.get('fees', []))} fees, "
        f"{len(r.get('sources', []))} sources"
    ),
)
async def get_card_details(slug: str) -> dict[str, Any]:
    """Return every verified fact about one card: fees, limits, benefits,
    eligibility, currencies and sources.

    Read the fee flags carefully before saying anything about cost:
      * `is_waived: true`  — the provider states this charge is nil.
      * `is_unknown: true` — the provider publishes no figure. This is NOT zero,
        and you must not describe it as free.
      * amount `null` with neither flag — unverified. Say so.
    """
    ctx = get_context()
    row = (
        await ctx.db.execute(select(Card).where(Card.slug == slug))
    ).scalar_one_or_none()
    if row is None:
        return {"error": {"code": "CARD_NOT_FOUND", "message": f"No card with slug '{slug}'."}}
    return card_detail(to_card_facts(row))
