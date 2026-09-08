"""Cost model arithmetic (BUILD.md section 78, "Cost")."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.enums import FeeType
from app.fx.models import FXRateTable
from app.recommendation.calculator import calculate_card_cost, calculate_costs, derive_usage
from app.schemas.profile import SpendEstimate, UserProfile
from tests.factories import gbp_inr_table, make_card


def profile(**overrides) -> UserProfile:
    base = dict(
        destination_currencies=["GBP"],
        trip_duration_months=12,
        monthly_spend=SpendEstimate(min_amount=Decimal(1000), max_amount=Decimal(1000), currency="GBP"),
        atm_usage="none",
        expected_reload_frequency=1,
    )
    base.update(overrides)
    return UserProfile(**base)


def component(breakdown, fee_type: FeeType):
    return next((c for c in breakdown.components if c.fee_type is fee_type), None)


def test_issuance_is_charged_once_not_per_month():
    card = make_card(name="C", issuance=Decimal(500), reload_fee=None, atm_fee=None, cross_currency_pct=None)
    cost = calculate_card_cost(card, profile(), gbp_inr_table())
    assert component(cost, FeeType.ISSUANCE).amount_inr == Decimal("500.00")


def test_reload_fee_multiplies_by_reload_count():
    card = make_card(name="C", issuance=None, reload_fee=Decimal(150), atm_fee=None, cross_currency_pct=None)
    cost = calculate_card_cost(card, profile(trip_duration_months=24), gbp_inr_table())
    # 24 months x 1 reload/month x ₹150
    assert component(cost, FeeType.RELOAD).amount_inr == Decimal("3600.00")


def test_atm_fee_multiplies_by_withdrawal_count():
    card = make_card(name="C", issuance=None, reload_fee=None, atm_fee=Decimal(200), cross_currency_pct=None)
    cost = calculate_card_cost(
        card, profile(atm_usage="unknown", atm_withdrawals_per_month=3), gbp_inr_table()
    )
    # 12 months x 3 withdrawals x ₹200
    assert component(cost, FeeType.ATM_WITHDRAWAL).amount_inr == Decimal("7200.00")


def test_cross_currency_applies_only_without_a_direct_wallet():
    with_wallet = make_card(name="Wallet", wallet_currencies=("GBP",), cross_currency_pct=Decimal("3.5"))
    without = make_card(name="No Wallet", wallet_currencies=("USD",), cross_currency_pct=Decimal("3.5"))

    fx = gbp_inr_table()
    costs = calculate_costs([with_wallet, without], profile(), fx)

    assert component(costs[str(with_wallet.id)], FeeType.CROSS_CURRENCY).amount_inr == Decimal("0.00")
    # 12 x £1,000 = £12,000 -> 3.5% = £420 -> x112.5 = ₹47,250
    assert component(costs[str(without.id)], FeeType.CROSS_CURRENCY).amount_inr == Decimal("47250.00")


def test_waived_fee_is_zero_and_unknown_fee_is_not():
    from app.recommendation.models import FeeFact

    waived = make_card(name="Waived", issuance=None, reload_fee=None, atm_fee=None, cross_currency_pct=None)
    waived = waived.model_copy(
        update={"fees": (FeeFact(fee_type=FeeType.ISSUANCE, is_waived=True, currency="INR"),)}
    )
    cost = calculate_card_cost(waived, profile(), gbp_inr_table())
    assert component(cost, FeeType.ISSUANCE).amount_inr == Decimal("0.00")

    unknown = make_card(name="Unknown", issuance=None, reload_fee=None, atm_fee=None, cross_currency_pct=None)
    unknown_cost = calculate_card_cost(unknown, profile(), gbp_inr_table())
    assert FeeType.ISSUANCE in unknown_cost.unknown_components
    assert unknown_cost.total_is_lower_bound


def test_missing_fee_is_imputed_from_the_worst_peer_not_zero():
    silent = make_card(name="Silent", issuance=None, reload_fee=Decimal(0), atm_fee=None, cross_currency_pct=None)
    loud = make_card(name="Loud", issuance=Decimal(3000), reload_fee=Decimal(0), atm_fee=None, cross_currency_pct=None)

    costs = calculate_costs([silent, loud], profile(), gbp_inr_table())
    silent_issuance = component(costs[str(silent.id)], FeeType.ISSUANCE)

    assert silent_issuance.amount_inr == Decimal("3000.00")
    assert silent_issuance.is_imputed
    assert "highest figure" in silent_issuance.imputation_note


def test_duration_scales_the_total():
    card = make_card(name="C", issuance=Decimal(500), reload_fee=Decimal(100), atm_fee=None, cross_currency_pct=None)
    fx = gbp_inr_table()

    twelve = calculate_card_cost(card, profile(trip_duration_months=12), fx)
    twentyfour = calculate_card_cost(card, profile(trip_duration_months=24), fx)

    # Issuance is one-off, reloads double: 500+1200 -> 500+2400
    assert twelve.total_inr == Decimal("1700.00")
    assert twentyfour.total_inr == Decimal("2900.00")


def test_total_is_also_expressed_in_the_spend_currency():
    card = make_card(name="C", issuance=Decimal("1125.00"), reload_fee=None, atm_fee=None, cross_currency_pct=None)
    cost = calculate_card_cost(card, profile(), gbp_inr_table())
    assert cost.spend_currency == "GBP"
    assert cost.total_spend_currency == Decimal("10.00")  # ₹1,125 / 112.5


def test_missing_fx_rate_does_not_silently_become_one_to_one():
    card = make_card(name="C", issuance=Decimal(500), reload_fee=None, atm_fee=None, cross_currency_pct=None)
    cost = calculate_card_cost(card, profile(), FXRateTable())
    assert cost.total_spend_currency is None


def test_zero_withdrawals_costs_nothing_for_atm():
    card = make_card(name="C", atm_fee=Decimal(500))
    cost = calculate_card_cost(card, profile(atm_usage="none", atm_withdrawals_per_month=0), gbp_inr_table())
    assert component(cost, FeeType.ATM_WITHDRAWAL).amount_inr == Decimal("0.00")


def test_usage_derivation_records_every_assumption():
    usage = derive_usage(UserProfile(destination_currencies=["GBP"]))
    assert usage.duration_months == 12
    assert any("12 months" in a for a in usage.assumptions)
