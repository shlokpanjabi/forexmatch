"""Hand-built card fixtures for engine tests.

Deliberately synthetic: these exist to exercise the arithmetic and the ranking
rules, and are never loaded into the catalogue. Real card data only ever enters
through the sourced seed files.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.enums import (
    BenefitType,
    CardNetwork,
    CardType,
    FeeType,
    SourceType,
)
from app.fx.models import FXRate, FXRateTable
from app.recommendation.models import (
    BenefitFact,
    CardFacts,
    CurrencyFact,
    FeeFact,
    SourceFact,
)

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def make_source(*, source_type: SourceType = SourceType.OFFICIAL_FEE_SCHEDULE, age_days: int = 1) -> SourceFact:
    moment = NOW - timedelta(days=age_days)
    return SourceFact(
        id=uuid.uuid4(),
        url="https://example.bank/fees",
        domain="example.bank",
        title="Fee schedule",
        source_type=source_type,
        retrieved_at=moment,
        last_verified_at=moment,
    )


def make_card(
    *,
    name: str,
    provider: str = "Test Bank",
    issuance: Decimal | None = Decimal(500),
    reload_fee: Decimal | None = Decimal(100),
    atm_fee: Decimal | None = Decimal(200),
    atm_fee_unknown: bool = False,
    cross_currency_pct: Decimal | None = Decimal("3.5"),
    wallet_currencies: tuple[str, ...] = ("GBP",),
    benefits: tuple[BenefitType, ...] = (),
    is_active: bool = True,
    application_url: str | None = "https://example.bank/apply",
    verified_age_days: int = 1,
    card_id: uuid.UUID | None = None,
) -> CardFacts:
    source = make_source(age_days=verified_age_days)
    fees: list[FeeFact] = []

    if issuance is not None:
        fees.append(FeeFact(fee_type=FeeType.ISSUANCE, amount=issuance, currency="INR"))
    if reload_fee is not None:
        fees.append(FeeFact(fee_type=FeeType.RELOAD, amount=reload_fee, currency="INR"))
    if atm_fee_unknown:
        fees.append(FeeFact(fee_type=FeeType.ATM_WITHDRAWAL, is_unknown=True))
    elif atm_fee is not None:
        fees.append(FeeFact(fee_type=FeeType.ATM_WITHDRAWAL, amount=atm_fee, currency="INR"))
    if cross_currency_pct is not None:
        fees.append(FeeFact(fee_type=FeeType.CROSS_CURRENCY, percentage=cross_currency_pct))

    return CardFacts(
        id=card_id or uuid.uuid4(),
        provider=provider,
        card_name=name,
        slug=name.lower().replace(" ", "-"),
        card_type=CardType.MULTI_CURRENCY_FOREX,
        network=CardNetwork.VISA,
        is_active=is_active,
        application_url=application_url,
        last_verified_at=NOW - timedelta(days=verified_age_days),
        currencies=tuple(
            CurrencyFact(currency_code=code, supported=True, direct_wallet=True)
            for code in wallet_currencies
        ),
        fees=tuple(fees),
        benefits=tuple(
            BenefitFact(benefit_type=b, description=b.value.replace("_", " ")) for b in benefits
        ),
        sources=(source,),
    )


def gbp_inr_table(rate: str = "112.50") -> FXRateTable:
    return FXRateTable(
        rates=(
            FXRate(
                base_currency="GBP",
                quote_currency="INR",
                rate=Decimal(rate),
                provider="test",
                retrieved_at=NOW,
            ),
        )
    )
