"""Card catalogue endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.db.models import Card, CardCurrency
from app.errors import NotFoundError
from app.recommendation.service import to_card_facts
from app.schemas.serializers import card_detail, card_summary

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("")
async def list_cards(
    db: DbSession,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    provider: str | None = None,
    include_inactive: bool = False,
) -> dict[str, Any]:
    stmt = select(Card)
    if not include_inactive:
        stmt = stmt.where(Card.is_active.is_(True))
    if provider:
        stmt = stmt.where(Card.provider.ilike(f"%{provider}%"))
    if currency:
        code = currency.upper()
        supports = select(CardCurrency.card_id).where(
            CardCurrency.currency_code == code, CardCurrency.supported.is_(True)
        )
        stmt = stmt.where(Card.id.in_(supports))
    rows = (await db.execute(stmt.order_by(Card.provider, Card.card_name))).scalars().unique().all()
    return {"count": len(rows), "cards": [card_summary(to_card_facts(r)) for r in rows]}


@router.get("/{slug}")
async def get_card(slug: str, db: DbSession) -> dict[str, Any]:
    row = (await db.execute(select(Card).where(Card.slug == slug))).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"No card with slug '{slug}'.")
    return card_detail(to_card_facts(row))
