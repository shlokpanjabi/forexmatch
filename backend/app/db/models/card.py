"""Card catalogue: the source of truth for every financial fact we quote.

Design rules enforced structurally here (BUILD.md sections 12, 58, 62, 63):

* Every fee, limit, benefit and eligibility row carries a NOT NULL ``source_id``.
  It is impossible to store an unsourced financial fact.
* Money and percentage columns are NULLABLE. ``NULL`` means "not verified", and
  is never to be read as zero.
* CHECK constraints reject negative fees and out-of-range percentages.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.enums import (
    BenefitType,
    CardNetwork,
    CardType,
    EligibilityCriterion,
    FeeType,
    LimitType,
    SourceType,
)

MONEY = Numeric(14, 4)
PERCENT = Numeric(9, 5)


def _enum_col(enum_cls: type, **kwargs):
    """Store enums as short strings with a CHECK constraint (portable, easy to migrate)."""
    from sqlalchemy import Enum as SAEnum

    return mapped_column(
        SAEnum(enum_cls, native_enum=False, length=40, values_callable=lambda e: [m.value for m in e]),
        **kwargs,
    )


class Card(Base, TimestampMixin):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_cards_slug"),
        Index("ix_cards_provider", "provider"),
        Index("ix_cards_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    card_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    card_type: Mapped[CardType] = _enum_col(CardType, nullable=False)
    network: Mapped[CardNetwork] = _enum_col(CardNetwork, nullable=False, default=CardNetwork.UNKNOWN)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    application_url: Mapped[str | None] = mapped_column(Text)
    affiliate_url: Mapped[str | None] = mapped_column(Text)
    affiliate_provider: Mapped[str | None] = mapped_column(String(120))
    affiliate_tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: Most recent verification across this card's facts; maintained by the seed
    #: and verification pipelines so freshness can be filtered in SQL.
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    currencies: Mapped[list[CardCurrency]] = relationship(
        back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )
    fees: Mapped[list[CardFee]] = relationship(
        back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )
    limits: Mapped[list[CardLimit]] = relationship(
        back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )
    benefits: Mapped[list[CardBenefit]] = relationship(
        back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )
    eligibility: Mapped[list[CardEligibility]] = relationship(
        back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )
    sources: Mapped[list[Source]] = relationship(
        back_populates="card", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Card {self.provider} — {self.card_name}>"


class Source(Base):
    """A retrievable document backing one or more card facts."""

    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_card_id", "card_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[SourceType] = _enum_col(SourceType, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)

    card: Mapped[Card] = relationship(back_populates="sources")


class CardCurrency(Base):
    __tablename__ = "card_currencies"
    __table_args__ = (
        UniqueConstraint("card_id", "currency_code", name="uq_card_currencies_card_id"),
        CheckConstraint("char_length(currency_code) = 3", name="currency_code_iso4217"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: True when the card holds a dedicated wallet in this currency (no cross-currency fee).
    direct_wallet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    card: Mapped[Card] = relationship(back_populates="currencies")
    source: Mapped[Source] = relationship()


class CardFee(Base):
    __tablename__ = "card_fees"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        CheckConstraint("min_amount IS NULL OR min_amount >= 0", name="min_amount_non_negative"),
        CheckConstraint("max_amount IS NULL OR max_amount >= 0", name="max_amount_non_negative"),
        CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 100)",
            name="percentage_in_range",
        ),
        CheckConstraint(
            "amount IS NOT NULL OR percentage IS NOT NULL OR is_unknown = true",
            name="fee_has_value_or_is_explicitly_unknown",
        ),
        Index("ix_card_fees_card_id_fee_type", "card_id", "fee_type"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    fee_type: Mapped[FeeType] = _enum_col(FeeType, nullable=False)

    #: Flat component, in ``currency``. NULL means unverified — never "free".
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str | None] = mapped_column(String(3))
    #: Percentage component (e.g. an FX markup or a percentage-of-value reload fee).
    percentage: Mapped[Decimal | None] = mapped_column(PERCENT)
    min_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    max_amount: Mapped[Decimal | None] = mapped_column(MONEY)

    #: Set when the provider publishes no figure. Keeps "we checked and it is
    #: undisclosed" distinguishable from "we never looked".
    is_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: True when the provider states the fee is genuinely nil.
    is_waived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    conditions: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    card: Mapped[Card] = relationship(back_populates="fees")
    source: Mapped[Source] = relationship()


class CardLimit(Base):
    __tablename__ = "card_limits"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        Index("ix_card_limits_card_id", "card_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    limit_type: Mapped[LimitType] = _enum_col(LimitType, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str | None] = mapped_column(String(3))
    period: Mapped[str | None] = mapped_column(String(40))
    conditions: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    card: Mapped[Card] = relationship(back_populates="limits")
    source: Mapped[Source] = relationship()


class CardBenefit(Base):
    __tablename__ = "card_benefits"
    __table_args__ = (Index("ix_card_benefits_card_id", "card_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    benefit_type: Mapped[BenefitType] = _enum_col(BenefitType, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(String(200))
    conditions: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    card: Mapped[Card] = relationship(back_populates="benefits")
    source: Mapped[Source] = relationship()


class CardEligibility(Base):
    __tablename__ = "card_eligibility"
    __table_args__ = (Index("ix_card_eligibility_card_id", "card_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), nullable=False
    )
    criterion: Mapped[EligibilityCriterion] = _enum_col(EligibilityCriterion, nullable=False)
    value: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )

    card: Mapped[Card] = relationship(back_populates="eligibility")
    source: Mapped[Source] = relationship()


class FXRateCache(Base):
    """Reference-rate cache. PostgreSQL, not Redis — BUILD.md section 21."""

    __tablename__ = "fx_rate_cache"
    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency", "provider", name="uq_fx_rate_cache_base_currency"),
        Index("ix_fx_rate_cache_retrieved_at", "retrieved_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: Date the provider says the rate refers to (reference rates are daily).
    rate_date: Mapped[date | None] = mapped_column(Date)
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
