"""FX service: caching, retries and graceful degradation.

Caching lives in PostgreSQL rather than Redis — one datastore is enough for the
rates involved (BUILD.md section 21).

When the upstream provider fails we retry once, then fall back to the last
cached rate *marked as cached and stale* (section 65). A stale rate is never
passed off as live, and if there is nothing cached at all the caller gets an
error rather than an invented number.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.card import FXRateCache
from app.fx.models import FXRate, FXRateTable
from app.fx.provider import FXProvider, FXProviderError, build_provider

logger = structlog.get_logger(__name__)

#: Beyond this, a cached rate is served but flagged as stale.
STALE_AFTER = timedelta(hours=48)


class FXService:
    """Fetches reference rates, caching them in PostgreSQL."""

    def __init__(self, session: AsyncSession, provider: FXProvider | None = None) -> None:
        settings = get_settings()
        self._session = session
        self._provider = provider or build_provider(settings.fx_provider, settings.fx_api_key)
        self._ttl = timedelta(seconds=settings.fx_cache_ttl_seconds)

    # --- Cache ---------------------------------------------------------------

    async def _read_cache(self, base: str, quote: str) -> tuple[FXRate, bool] | None:
        """Return (rate, is_fresh) from cache, or None when absent."""
        stmt = select(FXRateCache).where(
            FXRateCache.base_currency == base,
            FXRateCache.quote_currency == quote,
            FXRateCache.provider == self._provider.name,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        retrieved = row.retrieved_at
        if retrieved.tzinfo is None:
            retrieved = retrieved.replace(tzinfo=UTC)
        age = datetime.now(UTC) - retrieved
        is_fresh = age <= self._ttl

        return (
            FXRate(
                base_currency=row.base_currency,
                quote_currency=row.quote_currency,
                rate=row.rate,
                provider=row.provider,
                retrieved_at=retrieved,
                rate_date=row.rate_date,
                is_cached=True,
                is_stale=age > STALE_AFTER,
            ),
            is_fresh,
        )

    async def _write_cache(self, rate: FXRate) -> None:
        stmt = (
            pg_insert(FXRateCache)
            .values(
                base_currency=rate.base_currency,
                quote_currency=rate.quote_currency,
                rate=rate.rate,
                provider=rate.provider,
                retrieved_at=rate.retrieved_at,
                rate_date=rate.rate_date,
                ttl_seconds=int(self._ttl.total_seconds()),
            )
            .on_conflict_do_update(
                index_elements=["base_currency", "quote_currency", "provider"],
                set_={
                    "rate": rate.rate,
                    "retrieved_at": rate.retrieved_at,
                    "rate_date": rate.rate_date,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    # --- Public API ----------------------------------------------------------

    async def get_rate(self, base_currency: str, quote_currency: str) -> FXRate:
        """Fetch a reference rate, preferring cache within its TTL."""
        base, quote = base_currency.upper(), quote_currency.upper()
        if base == quote:
            return FXRate(
                base_currency=base,
                quote_currency=quote,
                rate=Decimal(1),
                provider="identity",
                retrieved_at=datetime.now(UTC),
            )

        cached = await self._read_cache(base, quote)
        if cached is not None and cached[1]:
            return cached[0]

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                rate = await self._provider.get_rate(base, quote)
            except FXProviderError as exc:
                last_error = exc
                logger.warning(
                    "fx.fetch_failed", pair=f"{base}/{quote}", attempt=attempt + 1, error=str(exc)
                )
                if attempt == 0:
                    await asyncio.sleep(0.4)
                continue
            await self._write_cache(rate)
            return rate

        if cached is not None:
            logger.warning("fx.serving_stale_cache", pair=f"{base}/{quote}")
            return cached[0]

        raise FXProviderError(
            f"no reference rate available for {base}/{quote} and nothing cached: {last_error}"
        )

    async def get_table(self, currencies: list[str], quote_currency: str = "INR") -> FXRateTable:
        """Build the rate table the recommendation engine consumes.

        Missing pairs are simply absent; the engine treats an absent rate as
        "cannot convert" rather than substituting 1.0.
        """
        wanted = [c.upper() for c in dict.fromkeys(currencies) if c and c.upper() != quote_currency.upper()]
        rates: list[FXRate] = []
        notes: list[str] = []

        for currency in wanted:
            try:
                rates.append(await self.get_rate(currency, quote_currency))
            except FXProviderError as exc:
                logger.warning("fx.pair_unavailable", pair=f"{currency}/{quote_currency}", error=str(exc))
                notes.append(f"No {currency}/{quote_currency} reference rate was available.")

        if any(r.is_stale for r in rates):
            notes.append("At least one rate is served from cache and may be out of date.")
        elif any(r.is_cached for r in rates):
            notes.append("Rates served from a recent cache.")

        return FXRateTable(rates=tuple(rates), base_note=" ".join(notes) or None)
