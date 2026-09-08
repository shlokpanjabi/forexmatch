"""Application and provenance tools."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from strands import tool

from app.agent.context import get_context, traced_tool
from app.db.models import Card
from app.recommendation.service import to_card_facts
from app.schemas.serializers import source_to_dict


@tool
@traced_tool(
    describe_input=lambda slug: slug,
    describe_output=lambda r: "application URL returned" if r.get("application_url") else "no route",
)
async def get_application_link(slug: str) -> dict[str, Any]:
    """Return the official application route for a card.

    Never invent or guess a URL. If this returns none, tell the user the
    provider does not publish an online application and point them at the
    provider instead.
    """
    ctx = get_context()
    row = (await ctx.db.execute(select(Card).where(Card.slug == slug))).scalar_one_or_none()
    if row is None:
        return {"error": {"code": "CARD_NOT_FOUND", "message": f"No card with slug '{slug}'."}}

    card = to_card_facts(row)
    return {
        "card": {"slug": card.slug, "provider": card.provider, "card_name": card.card_name},
        "application_url": card.apply_url,
        "official_url": card.application_url,
        # Present for disclosure only. Ranking never sees it (BUILD.md section 53).
        "is_affiliate": bool(card.affiliate_tracking_enabled and card.affiliate_url),
        "note": (
            "Opens the provider's own application flow. ForexMatch does not process "
            "applications and cannot issue a card."
        ),
    }


@tool
@traced_tool(
    describe_input=lambda slug: slug,
    describe_output=lambda r: f"{len(r.get('sources', []))} sources",
)
async def get_card_sources(slug: str) -> dict[str, Any]:
    """Return the documents backing a card's data, with verification dates.

    Cite these when you state a fee. If `freshness` is aging or stale, mention
    that the figures may have moved since they were last checked.
    """
    ctx = get_context()
    row = (await ctx.db.execute(select(Card).where(Card.slug == slug))).scalar_one_or_none()
    if row is None:
        return {"error": {"code": "CARD_NOT_FOUND", "message": f"No card with slug '{slug}'."}}

    card = to_card_facts(row)
    return {
        "card": {"slug": card.slug, "provider": card.provider, "card_name": card.card_name},
        "freshness": card.freshness.value,
        "last_verified_at": card.last_verified_at.isoformat() if card.last_verified_at else None,
        "sources": [source_to_dict(s) for s in card.sources],
        "official_source_count": len(card.official_sources),
    }
