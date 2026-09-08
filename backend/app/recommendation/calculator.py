"""Deterministic cost model (BUILD.md sections 18, 19, 58).

Turns a profile into an expected usage pattern, then prices each card against
it. Pure functions only — no database, no network, no LLM.

The central problem this module solves is *missing data*. A card whose ATM fee
is simply not published must not win by looking free. So costing runs in two
passes over the candidate set:

1. Price every component that can be priced; mark the rest as missing.
2. For each missing component, substitute the **highest** value any comparable
   card charges, flagged as imputed and explained in the output.

If no card in the set publishes that fee, the component is dropped from the
total and recorded in ``unknown_components`` — which makes the total an
explicit lower bound rather than a false figure.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.enums import FeeType, ValueConfidence
from app.fx.models import FXRateTable
from app.recommendation.models import CardFacts, CostBreakdown, CostComponent
from app.schemas.profile import UserProfile

INR = "INR"
TWO_PLACES = Decimal("0.01")

#: Charges we price for a typical study-abroad stay. Replacement and inactivity
#: are excluded by default: neither is expected usage, and including them would
#: penalise cards that merely document them (BUILD.md section 18).
DEFAULT_RELEVANT_FEES: tuple[FeeType, ...] = (
    FeeType.ISSUANCE,
    FeeType.RELOAD,
    FeeType.ATM_WITHDRAWAL,
    FeeType.CROSS_CURRENCY,
)

FEE_LABELS: dict[FeeType, str] = {
    FeeType.ISSUANCE: "Card issuance",
    FeeType.RELOAD: "Reloads",
    FeeType.ATM_WITHDRAWAL: "ATM withdrawals",
    FeeType.CROSS_CURRENCY: "Cross-currency charges",
    FeeType.REPLACEMENT: "Replacement",
    FeeType.INACTIVITY: "Inactivity",
    FeeType.ENCASHMENT: "Encashment",
    FeeType.BALANCE_ENQUIRY: "Balance enquiries",
    FeeType.TRANSACTION: "Per-transaction charges",
    FeeType.OTHER: "Other charges",
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class UsageProfile:
    """Expected usage over the whole stay, derived from the user's answers."""

    duration_months: int
    spend_currency: str
    monthly_spend: Decimal | None
    total_spend: Decimal | None
    reloads_total: int
    atm_withdrawals_total: int
    average_atm_withdrawal: Decimal | None
    assumptions: tuple[str, ...] = ()

    @property
    def total_atm_cash(self) -> Decimal | None:
        if self.average_atm_withdrawal is None:
            return None
        return self.average_atm_withdrawal * self.atm_withdrawals_total


def derive_usage(profile: UserProfile) -> UsageProfile:
    """Expand a profile into concrete expected quantities.

    Every substituted value is recorded as an assumption so the UI can show its
    working (BUILD.md section 33).
    """
    assumptions: list[str] = []

    months = profile.effective_duration_months
    if profile.duration_is_assumed:
        assumptions.append("No trip length given, so costs are shown over 12 months for comparability.")

    currency = profile.primary_currency or INR
    monthly = profile.monthly_spend.midpoint
    total_spend = monthly * months if monthly is not None else None

    if monthly is not None and profile.monthly_spend.confidence is not ValueConfidence.STATED:
        described = profile.monthly_spend.describe()
        assumptions.append(
            f"Monthly spend treated as {described} (midpoint {currency} {monthly:,.0f}) — an estimate, not a stated figure."
        )

    withdrawals_pm, atm_conf = profile.effective_atm_withdrawals_per_month()
    withdrawals_total = withdrawals_pm * months
    if atm_conf is not ValueConfidence.STATED:
        assumptions.append(
            f"ATM use taken as about {withdrawals_pm} withdrawal(s) a month "
            f"({withdrawals_total} over {months} months), inferred from '{profile.atm_usage.value}'."
        )

    reloads_pm, reload_conf = profile.effective_reloads_per_month()
    reloads_total = reloads_pm * months
    if reload_conf is not ValueConfidence.STATED:
        assumptions.append(f"Assumed {reloads_pm} reload per month ({reloads_total} in total).")

    average_withdrawal = profile.average_atm_withdrawal
    if average_withdrawal is None and monthly is not None and withdrawals_pm > 0:
        # Cash is assumed to be a fifth of monthly spend, split across withdrawals.
        average_withdrawal = (monthly * Decimal("0.2") / withdrawals_pm).quantize(TWO_PLACES)
        assumptions.append(
            f"Average withdrawal assumed at {currency} {average_withdrawal:,.0f} "
            "(about a fifth of monthly spend taken as cash)."
        )

    return UsageProfile(
        duration_months=months,
        spend_currency=currency,
        monthly_spend=monthly,
        total_spend=total_spend,
        reloads_total=reloads_total,
        atm_withdrawals_total=withdrawals_total,
        average_atm_withdrawal=average_withdrawal,
        assumptions=tuple(assumptions),
    )


@dataclass
class _PricedComponent:
    """Intermediate result before cross-card imputation."""

    fee_type: FeeType
    amount_inr: Decimal | None
    basis: str
    missing_reason: str | None = None


@dataclass
class _CardPricing:
    card: CardFacts
    components: list[_PricedComponent] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    fx_label: str | None = None
    fx_retrieved_at: object | None = None


def _convert(amount: Decimal, currency: str, fx: FXRateTable) -> Decimal | None:
    if currency.upper() == INR:
        return amount
    return fx.convert(amount, currency, INR)


def _price_flat_and_percentage(
    *,
    flat: Decimal | None,
    flat_currency: str | None,
    percentage: Decimal | None,
    base_amount: Decimal | None,
    base_currency: str,
    occurrences: int,
    minimum: Decimal | None,
    maximum: Decimal | None,
    fx: FXRateTable,
) -> tuple[Decimal | None, str | None]:
    """Price one charge in INR. Returns (amount, failure_reason)."""
    per_occurrence = Decimal(0)
    have_value = False

    if flat is not None:
        currency = flat_currency or INR
        converted = _convert(flat, currency, fx)
        if converted is None:
            return None, f"no {currency}/INR rate available"
        per_occurrence += converted
        have_value = True

    if percentage is not None:
        if base_amount is None:
            return None, "transaction value unknown"
        pct_component = base_amount * percentage / Decimal(100)
        if minimum is not None:
            pct_component = max(pct_component, minimum)
        if maximum is not None:
            pct_component = min(pct_component, maximum)
        converted = _convert(pct_component, base_currency, fx)
        if converted is None:
            return None, f"no {base_currency}/INR rate available"
        per_occurrence += converted
        have_value = True

    if not have_value:
        return None, "not published"
    return per_occurrence * occurrences, None


def _price_card(card: CardFacts, usage: UsageProfile, fx: FXRateTable) -> _CardPricing:
    pricing = _CardPricing(card=card)
    currency = usage.spend_currency

    rate = fx.find(currency, INR)
    if rate is not None and currency != INR:
        pricing.fx_label = f"{rate.label} {rate.rate:.4f} ({rate.provider})"
        pricing.fx_retrieved_at = rate.retrieved_at

    # --- Issuance (one-off) -------------------------------------------------
    issuance = card.fee(FeeType.ISSUANCE)
    if issuance is None or not issuance.is_known:
        pricing.components.append(
            _PricedComponent(FeeType.ISSUANCE, None, "one-off issuance fee", "not published")
        )
    else:
        amount, reason = _price_flat_and_percentage(
            flat=issuance.effective_amount,
            flat_currency=issuance.currency,
            percentage=None,
            base_amount=None,
            base_currency=currency,
            occurrences=1,
            minimum=None,
            maximum=None,
            fx=fx,
        )
        basis = "issued once, fee waived" if issuance.is_waived else "one-off issuance fee"
        pricing.components.append(_PricedComponent(FeeType.ISSUANCE, amount, basis, reason))

    # --- Reloads ------------------------------------------------------------
    reload_fee = card.fee(FeeType.RELOAD)
    reload_value = usage.monthly_spend  # one month's spend loaded per reload
    if reload_fee is None or not reload_fee.is_known:
        pricing.components.append(
            _PricedComponent(
                FeeType.RELOAD, None, f"{usage.reloads_total} reloads", "not published"
            )
        )
    else:
        amount, reason = _price_flat_and_percentage(
            flat=reload_fee.effective_amount,
            flat_currency=reload_fee.currency,
            percentage=reload_fee.effective_percentage,
            base_amount=reload_value,
            base_currency=currency,
            occurrences=usage.reloads_total,
            minimum=reload_fee.min_amount,
            maximum=reload_fee.max_amount,
            fx=fx,
        )
        pricing.components.append(
            _PricedComponent(
                FeeType.RELOAD,
                amount,
                f"{usage.reloads_total} reloads over {usage.duration_months} months",
                reason,
            )
        )

    # --- ATM withdrawals ----------------------------------------------------
    # Per-currency ATM pricing is the norm, so ask for the currency in hand.
    atm_fee = card.fee(FeeType.ATM_WITHDRAWAL, currency=currency)
    if usage.atm_withdrawals_total == 0:
        pricing.components.append(
            _PricedComponent(FeeType.ATM_WITHDRAWAL, Decimal(0), "no cash withdrawals expected")
        )
    elif atm_fee is None or not atm_fee.is_known:
        pricing.components.append(
            _PricedComponent(
                FeeType.ATM_WITHDRAWAL,
                None,
                f"{usage.atm_withdrawals_total} withdrawals",
                "not published",
            )
        )
    else:
        amount, reason = _price_flat_and_percentage(
            flat=atm_fee.effective_amount,
            flat_currency=atm_fee.currency,
            percentage=atm_fee.effective_percentage,
            base_amount=usage.average_atm_withdrawal,
            base_currency=currency,
            occurrences=usage.atm_withdrawals_total,
            minimum=atm_fee.min_amount,
            maximum=atm_fee.max_amount,
            fx=fx,
        )
        pricing.components.append(
            _PricedComponent(
                FeeType.ATM_WITHDRAWAL,
                amount,
                f"{usage.atm_withdrawals_total} withdrawals over {usage.duration_months} months",
                reason,
            )
        )

    # --- Cross-currency -----------------------------------------------------
    # Only bites when the card has no wallet in the currency being spent.
    if not card.currencies:
        # We have not verified which currencies this card holds. Asserting that
        # it does not hold the user's currency would be inventing a fact, so the
        # component is left unknown and imputed like any other missing figure.
        pricing.components.append(
            _PricedComponent(
                FeeType.CROSS_CURRENCY,
                None,
                f"unverified whether this card holds {currency}",
                "supported currencies not verified",
            )
        )
    elif card.has_direct_wallet(currency):
        pricing.components.append(
            _PricedComponent(
                FeeType.CROSS_CURRENCY,
                Decimal(0),
                f"{currency} held directly on the card, so no cross-currency charge",
            )
        )
    else:
        cross_fee = card.fee(FeeType.CROSS_CURRENCY)
        if cross_fee is None or not cross_fee.is_known:
            pricing.components.append(
                _PricedComponent(
                    FeeType.CROSS_CURRENCY,
                    None,
                    f"all {currency} spend converted",
                    "not published",
                )
            )
        else:
            amount, reason = _price_flat_and_percentage(
                flat=cross_fee.effective_amount,
                flat_currency=cross_fee.currency,
                percentage=cross_fee.effective_percentage,
                base_amount=usage.total_spend,
                base_currency=currency,
                occurrences=1,
                minimum=None,
                maximum=None,
                fx=fx,
            )
            pricing.components.append(
                _PricedComponent(
                    FeeType.CROSS_CURRENCY,
                    amount,
                    f"{currency} not held on this card, so all spend is converted",
                    reason,
                )
            )
            pricing.assumptions.append(
                f"{card.card_name} does not hold {currency}, so every purchase incurs its "
                "cross-currency charge."
            )

    return pricing


def calculate_costs(
    cards: Sequence[CardFacts],
    profile: UserProfile,
    fx: FXRateTable,
    *,
    usage: UsageProfile | None = None,
) -> dict[str, CostBreakdown]:
    """Price every card against one usage profile, keyed by card id.

    Costed as a set rather than card-by-card so that a component missing on one
    card can be imputed from what its competitors charge.
    """
    usage = usage or derive_usage(profile)
    priced = [_price_card(card, usage, fx) for card in cards]

    # Worst published cost per component, used for pessimistic imputation.
    worst: dict[FeeType, Decimal] = {}
    for entry in priced:
        for component in entry.components:
            if component.amount_inr is None:
                continue
            current = worst.get(component.fee_type)
            if current is None or component.amount_inr > current:
                worst[component.fee_type] = component.amount_inr

    results: dict[str, CostBreakdown] = {}
    for entry in priced:
        components: list[CostComponent] = []
        unknown: list[FeeType] = []
        imputed: list[FeeType] = []
        total = Decimal(0)

        for component in entry.components:
            label = FEE_LABELS.get(component.fee_type, component.fee_type.value)
            if component.amount_inr is not None:
                amount = _money(component.amount_inr)
                total += amount
                components.append(
                    CostComponent(
                        fee_type=component.fee_type,
                        label=label,
                        amount_inr=amount,
                        basis=component.basis,
                    )
                )
                continue

            substitute = worst.get(component.fee_type)
            if substitute is None:
                unknown.append(component.fee_type)
                continue

            amount = _money(substitute)
            total += amount
            imputed.append(component.fee_type)
            components.append(
                CostComponent(
                    fee_type=component.fee_type,
                    label=label,
                    amount_inr=amount,
                    basis=component.basis,
                    is_imputed=True,
                    imputation_note=(
                        f"{entry.card.provider} does not publish this charge "
                        f"({component.missing_reason}); the highest figure among the compared "
                        f"cards (₹{amount:,.0f}) was used instead of assuming it is free."
                    ),
                )
            )

        assumptions = list(usage.assumptions) + entry.assumptions
        if unknown:
            names = ", ".join(FEE_LABELS.get(f, f.value).lower() for f in unknown)
            assumptions.append(
                f"No card in this comparison publishes {names}, so it is excluded — "
                "the total below is a lower bound."
            )

        total_in_spend_currency = None
        if usage.spend_currency != INR:
            total_in_spend_currency = fx.convert(total, INR, usage.spend_currency)
            if total_in_spend_currency is not None:
                total_in_spend_currency = _money(total_in_spend_currency)

        results[str(entry.card.id)] = CostBreakdown(
            card_id=entry.card.id,
            components=tuple(components),
            total_inr=_money(total),
            total_spend_currency=total_in_spend_currency,
            spend_currency=usage.spend_currency,
            duration_months=usage.duration_months,
            unknown_components=tuple(unknown),
            imputed_components=tuple(imputed),
            assumptions=tuple(dict.fromkeys(assumptions)),
            fx_rate_used=entry.fx_label,
            fx_retrieved_at=entry.fx_retrieved_at,
        )

    return results


def calculate_card_cost(
    card: CardFacts,
    profile: UserProfile,
    fx: FXRateTable,
    *,
    peers: Iterable[CardFacts] = (),
) -> CostBreakdown:
    """Cost a single card. ``peers`` supply the imputation baseline."""
    candidates = [card, *[p for p in peers if p.id != card.id]]
    return calculate_costs(candidates, profile, fx)[str(card.id)]
