"""FX tool — current reference rates."""

from __future__ import annotations

from typing import Any

from strands import tool

from app.agent.context import get_context, traced_tool
from app.fx.provider import FXProviderError
from app.fx.service import FXService


@tool
@traced_tool(
    describe_input=lambda base_currency, quote_currency="INR": f"{base_currency}/{quote_currency}",
    describe_output=lambda r: (
        f"{r.get('pair')} = {r.get('rate')}" if r.get("status") == "ok" else "rate unavailable"
    ),
)
async def get_fx_rate(base_currency: str, quote_currency: str = "INR") -> dict[str, Any]:
    """Get the current mid-market reference rate for a currency pair.

    This is a *reference* rate, not the rate any card issuer will give you. When
    you quote it, say so — a provider's own rate includes a markup, and the two
    must never be presented as the same number.
    """
    ctx = get_context()
    try:
        rate = await FXService(ctx.db).get_rate(base_currency, quote_currency)
    except FXProviderError as exc:
        return {
            "status": "unavailable",
            "pair": f"{base_currency.upper()}/{quote_currency.upper()}",
            "error": {"code": "FX_PROVIDER_UNAVAILABLE", "message": str(exc)},
        }

    return {
        "status": "ok",
        "pair": rate.label,
        "rate": str(rate.rate),
        "rate_type": "mid_market_reference",
        "provider": rate.provider,
        "retrieved_at": rate.retrieved_at.isoformat(),
        "rate_date": rate.rate_date.isoformat() if rate.rate_date else None,
        "is_cached": rate.is_cached,
        "is_stale": rate.is_stale,
        "note": (
            "Mid-market reference rate. A card issuer's own rate will differ; do not "
            "present this as the rate the user will receive."
        ),
    }
