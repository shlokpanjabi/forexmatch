"""FX types.

BUILD.md section 19 insists on keeping three things apart, and this module makes
conflating them awkward:

* ``reference_rate`` — mid-market rate from a public source.
* ``provider_rate``  — the rate a card issuer actually gives you.
* ``markup_percentage`` — the spread between the two.

We only ever *retrieve* reference rates. A provider rate is recorded only when a
provider publishes one; it is never inferred from a reference rate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FXRate(BaseModel):
    """A mid-market reference rate: 1 ``base_currency`` = ``rate`` ``quote_currency``."""

    model_config = ConfigDict(frozen=True)

    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=0)
    provider: str
    retrieved_at: datetime
    rate_date: date | None = None
    #: True when served from cache after a live fetch failed (BUILD.md section 65).
    is_cached: bool = False
    is_stale: bool = False

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @property
    def label(self) -> str:
        return f"{self.base_currency}/{self.quote_currency}"

    def inverted(self) -> FXRate:
        return FXRate(
            base_currency=self.quote_currency,
            quote_currency=self.base_currency,
            rate=Decimal(1) / self.rate,
            provider=self.provider,
            retrieved_at=self.retrieved_at,
            rate_date=self.rate_date,
            is_cached=self.is_cached,
            is_stale=self.is_stale,
        )


class ProviderFXTerms(BaseModel):
    """What a card issuer publishes about its own conversion.

    ``markup_percentage`` is only populated when the provider states it. A card
    with no published markup gets ``None`` — never 0 (BUILD.md section 58).
    """

    model_config = ConfigDict(frozen=True)

    markup_percentage: Decimal | None = None
    provider_rate: Decimal | None = None
    is_published: bool = False
    note: str | None = None


class FXRateTable(BaseModel):
    """Immutable set of rates handed to the pure recommendation engine.

    Passing rates in (rather than letting the engine fetch them) is what keeps
    ``recommend()`` deterministic and unit-testable — BUILD.md section 95.
    """

    model_config = ConfigDict(frozen=True)

    rates: tuple[FXRate, ...] = ()
    base_note: str | None = None

    def find(self, base: str, quote: str) -> FXRate | None:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return FXRate(
                base_currency=base,
                quote_currency=quote,
                rate=Decimal(1),
                provider="identity",
                retrieved_at=datetime.now(UTC),
            )
        for rate in self.rates:
            if rate.base_currency == base and rate.quote_currency == quote:
                return rate
        for rate in self.rates:
            if rate.base_currency == quote and rate.quote_currency == base:
                return rate.inverted()
        # One hop through a shared currency (e.g. GBP→INR via USD).
        for first in self.rates:
            for second in self.rates:
                if first.base_currency == base and second.quote_currency == quote:
                    if first.quote_currency == second.base_currency:
                        return FXRate(
                            base_currency=base,
                            quote_currency=quote,
                            rate=first.rate * second.rate,
                            provider=f"{first.provider}+derived",
                            retrieved_at=min(first.retrieved_at, second.retrieved_at),
                            is_cached=first.is_cached or second.is_cached,
                            is_stale=first.is_stale or second.is_stale,
                        )
        return None

    def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal | None:
        """Convert, or return None when no rate is available.

        Returning None rather than falling back to 1.0 keeps a missing rate from
        silently masquerading as a valid figure.
        """
        rate = self.find(from_currency, to_currency)
        return None if rate is None else amount * rate.rate

    @property
    def is_empty(self) -> bool:
        return not self.rates
