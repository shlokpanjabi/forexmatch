"""Reference-rate providers behind a single interface (BUILD.md section 20).

The application depends on the ``FXProvider`` protocol, never on a specific
vendor, so swapping source is a config change.

Everything here returns *reference* (mid-market) rates. No provider here can
tell you what a card issuer will actually give you — that distinction is the
whole point of ``app.fx.models`` and is preserved end to end.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

import httpx
import structlog

from app.fx.models import FXRate

logger = structlog.get_logger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


class FXProviderError(RuntimeError):
    """Raised when a provider cannot supply a rate."""


@runtime_checkable
class FXProvider(Protocol):
    name: str

    async def get_rate(self, base_currency: str, quote_currency: str) -> FXRate: ...


class FrankfurterProvider:
    """Frankfurter — ECB reference rates, no API key required.

    Publishes one rate per working day, so the ``rate_date`` it returns can
    legitimately be a day or two old at a weekend. We surface that date rather
    than implying the rate is intraday.
    """

    name = "frankfurter"
    BASE_URL = "https://api.frankfurter.dev/v1"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def get_rate(self, base_currency: str, quote_currency: str) -> FXRate:
        base, quote = base_currency.upper(), quote_currency.upper()
        params = {"base": base, "symbols": quote}
        try:
            if self._client is not None:
                response = await self._client.get(f"{self.BASE_URL}/latest", params=params)
            else:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.get(f"{self.BASE_URL}/latest", params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FXProviderError(f"frankfurter request failed: {exc}") from exc

        rates = payload.get("rates") or {}
        if quote not in rates:
            raise FXProviderError(f"frankfurter does not quote {base}/{quote}")

        try:
            rate = Decimal(str(rates[quote]))
        except InvalidOperation as exc:
            raise FXProviderError(f"unparseable rate for {base}/{quote}") from exc

        rate_date = None
        if isinstance(payload.get("date"), str):
            try:
                rate_date = date.fromisoformat(payload["date"])
            except ValueError:
                rate_date = None

        return FXRate(
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            provider=self.name,
            retrieved_at=datetime.now(UTC),
            rate_date=rate_date,
        )


class ExchangeRateHostProvider:
    """exchangerate.host — alternative source, API key required."""

    name = "exchangerate_host"
    BASE_URL = "https://api.exchangerate.host"

    def __init__(self, api_key: str | None, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client

    async def get_rate(self, base_currency: str, quote_currency: str) -> FXRate:
        if not self._api_key:
            raise FXProviderError("exchangerate_host selected but FX_API_KEY is not set")

        base, quote = base_currency.upper(), quote_currency.upper()
        params = {"access_key": self._api_key, "source": base, "currencies": quote}
        try:
            if self._client is not None:
                response = await self._client.get(f"{self.BASE_URL}/live", params=params)
            else:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.get(f"{self.BASE_URL}/live", params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FXProviderError(f"exchangerate.host request failed: {exc}") from exc

        if not payload.get("success", False):
            raise FXProviderError(f"exchangerate.host error: {payload.get('error')}")

        key = f"{base}{quote}"
        quotes = payload.get("quotes") or {}
        if key not in quotes:
            raise FXProviderError(f"exchangerate.host does not quote {base}/{quote}")

        return FXRate(
            base_currency=base,
            quote_currency=quote,
            rate=Decimal(str(quotes[key])),
            provider=self.name,
            retrieved_at=datetime.now(UTC),
        )


class StaticProvider:
    """Fixed rates for tests and offline development.

    Rates supplied here are explicitly labelled as such downstream so a demo can
    never present them as live market data.
    """

    name = "static"

    def __init__(self, rates: dict[tuple[str, str], Decimal] | None = None) -> None:
        self._rates = rates or {}

    async def get_rate(self, base_currency: str, quote_currency: str) -> FXRate:
        base, quote = base_currency.upper(), quote_currency.upper()
        rate = self._rates.get((base, quote))
        if rate is None:
            inverse = self._rates.get((quote, base))
            if inverse is not None:
                rate = Decimal(1) / inverse
        if rate is None:
            raise FXProviderError(f"no static rate configured for {base}/{quote}")
        return FXRate(
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            provider=self.name,
            retrieved_at=datetime.now(UTC),
        )


def build_provider(name: str, api_key: str | None = None) -> FXProvider:
    if name == "frankfurter":
        return FrankfurterProvider()
    if name == "exchangerate_host":
        return ExchangeRateHostProvider(api_key)
    if name == "static":
        return StaticProvider()
    raise ValueError(f"unknown FX provider: {name}")
