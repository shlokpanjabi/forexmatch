"""Research tool — checks a provider's current published information."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from strands import tool

from app.agent.context import get_context, traced_tool
from app.db.models import Card
from app.research.service import ResearchService


@tool
@traced_tool(
    describe_input=lambda slug, topic="fees and charges": f"{slug}: {topic}",
    describe_output=lambda r: (
        f"{len(r.get('findings', []))} sources found"
        if r.get("status") == "ok"
        else "research unavailable"
    ),
)
async def research_card(slug: str, topic: str = "fees and charges") -> dict[str, Any]:
    """Look up a provider's current published information for one card.

    Use this when a card's data is stale or a key figure is missing — not for
    every card. Searching is slow, so research the few cards that actually
    matter to this user's shortlist.

    If the result is `unavailable`, say that current figures could not be
    re-checked and rely on the stored data. Never fill the gap from memory: an
    invented fee is worse than an acknowledged unknown.
    """
    ctx = get_context()
    row = (await ctx.db.execute(select(Card).where(Card.slug == slug))).scalar_one_or_none()
    if row is None:
        return {"error": {"code": "CARD_NOT_FOUND", "message": f"No card with slug '{slug}'."}}

    result = await ResearchService().search(row.provider, row.card_name, topic)
    payload = result.to_dict()
    payload["card"] = {"slug": row.slug, "provider": row.provider, "card_name": row.card_name}
    payload["stored_last_verified_at"] = (
        row.last_verified_at.isoformat() if row.last_verified_at else None
    )
    return payload
