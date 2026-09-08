"""Database ↔ engine boundary.

Loads ORM rows into the frozen ``CardFacts`` snapshots the engine consumes, and
runs the ranking. Keeping the translation here is what lets the engine itself
stay pure and unit-testable.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Card
from app.fx.models import FXRateTable
from app.fx.provider import FXProviderError
from app.fx.service import FXService
from app.recommendation.engine import recommend
from app.recommendation.models import (
    BenefitFact,
    CardFacts,
    CurrencyFact,
    EligibilityFact,
    FeeFact,
    LimitFact,
    RecommendationResult,
    SourceFact,
)
from app.schemas.profile import UserProfile

logger = structlog.get_logger(__name__)


def to_card_facts(card: Card) -> CardFacts:
    """Freeze an ORM row into the engine's immutable snapshot."""
    return CardFacts(
        id=card.id,
        provider=card.provider,
        card_name=card.card_name,
        slug=card.slug,
        card_type=card.card_type,
        network=card.network,
        description=card.description,
        is_active=card.is_active,
        application_url=card.application_url,
        affiliate_url=card.affiliate_url,
        affiliate_tracking_enabled=card.affiliate_tracking_enabled,
        last_verified_at=card.last_verified_at,
        currencies=tuple(
            CurrencyFact(
                currency_code=c.currency_code, supported=c.supported, direct_wallet=c.direct_wallet
            )
            for c in card.currencies
        ),
        fees=tuple(
            FeeFact(
                fee_type=f.fee_type,
                amount=f.amount,
                currency=f.currency,
                percentage=f.percentage,
                min_amount=f.min_amount,
                max_amount=f.max_amount,
                is_unknown=f.is_unknown,
                is_waived=f.is_waived,
                conditions=f.conditions,
            )
            for f in card.fees
        ),
        limits=tuple(
            LimitFact(limit_type=l.limit_type, amount=l.amount, currency=l.currency, period=l.period)
            for l in card.limits
        ),
        benefits=tuple(
            BenefitFact(benefit_type=b.benefit_type, description=b.description, value=b.value)
            for b in card.benefits
        ),
        eligibility=tuple(
            EligibilityFact(criterion=e.criterion, value=e.value, description=e.description)
            for e in card.eligibility
        ),
        sources=tuple(
            SourceFact(
                id=s.id,
                url=s.url,
                domain=s.domain,
                title=s.title,
                source_type=s.source_type,
                retrieved_at=s.retrieved_at,
                last_verified_at=s.last_verified_at,
            )
            for s in card.sources
        ),
    )


async def load_cards(
    session: AsyncSession,
    *,
    active_only: bool = True,
    card_ids: Sequence[uuid.UUID] | None = None,
    slugs: Sequence[str] | None = None,
) -> list[CardFacts]:
    stmt = select(Card)
    if active_only:
        stmt = stmt.where(Card.is_active.is_(True))
    if card_ids:
        stmt = stmt.where(Card.id.in_(card_ids))
    if slugs:
        stmt = stmt.where(Card.slug.in_(slugs))
    stmt = stmt.order_by(Card.provider, Card.card_name)
    rows = (await session.execute(stmt)).scalars().unique().all()
    return [to_card_facts(row) for row in rows]


class RecommendationService:
    """Fetches the catalogue and today's rates, then runs the pure engine."""

    def __init__(self, session: AsyncSession, fx_service: FXService | None = None) -> None:
        self._session = session
        self._fx = fx_service or FXService(session)

    async def build_fx_table(self, profile: UserProfile) -> FXRateTable:
        """Rates for the user's currencies, plus the majors most cards price in."""
        wanted = list(profile.destination_currencies)
        if profile.monthly_spend.currency:
            wanted.append(profile.monthly_spend.currency)
        # Fees are commonly denominated in USD even on non-USD cards.
        wanted.append("USD")
        try:
            return await self._fx.get_table(wanted, quote_currency="INR")
        except FXProviderError as exc:
            logger.warning("fx.table_unavailable", error=str(exc))
            return FXRateTable(base_note="Live reference rates were unavailable for this comparison.")

    async def recommend_for_profile(
        self,
        profile: UserProfile,
        *,
        card_ids: Sequence[uuid.UUID] | None = None,
        max_results: int = 3,
    ) -> RecommendationResult:
        cards = await load_cards(self._session, card_ids=card_ids)
        fx = await self.build_fx_table(profile)
        result = recommend(profile, cards, fx, max_results=max_results)
        logger.info(
            "recommendation.generated",
            candidates=len(cards),
            compared=len(result.comparison),
            excluded=len(result.excluded),
            confidence=result.confidence.value,
            winner=result.recommended.card.slug if result.recommended else None,
        )
        return result
