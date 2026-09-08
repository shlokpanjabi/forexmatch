"""Ranking behaviour (BUILD.md section 78)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.enums import BenefitType, Confidence, ScoreComponent
from app.recommendation.engine import recommend
from app.schemas.profile import PriorityWeights, SpendEstimate, UserProfile
from tests.factories import gbp_inr_table, make_card


@pytest.fixture
def uk_student_profile() -> UserProfile:
    """The BUILD.md section 80 demo user."""
    return UserProfile(
        destination_country="United Kingdom",
        destination_currencies=["GBP"],
        trip_duration_months=24,
        monthly_spend=SpendEstimate(min_amount=Decimal(1000), max_amount=Decimal(1200), currency="GBP"),
        atm_usage="low",
        student_status=True,
    )


def test_lowest_cost_card_wins_when_cost_dominates(uk_student_profile):
    cheap = make_card(name="Cheap Card", issuance=Decimal(0), reload_fee=Decimal(0), atm_fee=Decimal(100))
    dear = make_card(name="Dear Card", issuance=Decimal(2000), reload_fee=Decimal(300), atm_fee=Decimal(600))

    uk_student_profile.priorities = PriorityWeights(
        cost=1.0, atm=0.0, currency_support=0.0, convenience=0.0, rewards=0.0, security=0.0
    )
    result = recommend(uk_student_profile, [cheap, dear], gbp_inr_table())

    assert result.recommended.card.card_name == "Cheap Card"
    assert result.recommended.cost.total_inr < result.comparison[1].cost.total_inr


def test_atm_heavy_user_favours_low_atm_fee(uk_student_profile):
    low_atm = make_card(name="Low ATM", issuance=Decimal(1000), atm_fee=Decimal(0))
    high_atm = make_card(name="High ATM", issuance=Decimal(0), atm_fee=Decimal(700))

    uk_student_profile.atm_withdrawals_per_month = 12
    result = recommend(uk_student_profile, [low_atm, high_atm], gbp_inr_table())

    assert result.recommended.card.card_name == "Low ATM"


def test_rewards_priority_changes_the_winner(uk_student_profile):
    plain = make_card(name="Plain Card", issuance=Decimal(0), reload_fee=Decimal(0))
    rich = make_card(
        name="Rewards Card",
        issuance=Decimal(1500),
        benefits=(BenefitType.LOUNGE_ACCESS, BenefitType.CASHBACK, BenefitType.INSURANCE),
    )

    cost_first = recommend(uk_student_profile, [plain, rich], gbp_inr_table())
    assert cost_first.recommended.card.card_name == "Plain Card"

    uk_student_profile.priorities = PriorityWeights(
        cost=0.0, atm=0.0, currency_support=0.1, convenience=0.0, rewards=0.9, security=0.0
    )
    uk_student_profile.priorities_customised = True
    rewards_first = recommend(uk_student_profile, [plain, rich], gbp_inr_table())
    assert rewards_first.recommended.card.card_name == "Rewards Card"


def test_currency_mismatch_is_penalised(uk_student_profile):
    gbp_wallet = make_card(name="GBP Wallet", wallet_currencies=("GBP",))
    usd_only = make_card(name="USD Only", wallet_currencies=("USD",), cross_currency_pct=Decimal("3.5"))

    result = recommend(uk_student_profile, [gbp_wallet, usd_only], gbp_inr_table())

    winner_currency = result.recommended.score_for(ScoreComponent.CURRENCY_SUPPORT)
    loser = next(e for e in result.comparison if e.card.card_name == "USD Only")
    assert result.recommended.card.card_name == "GBP Wallet"
    assert winner_currency.score > loser.score_for(ScoreComponent.CURRENCY_SUPPORT).score


def test_weights_are_normalised(uk_student_profile):
    uk_student_profile.priorities = PriorityWeights(
        cost=4.0, atm=1.0, currency_support=1.0, convenience=1.0, rewards=2.0, security=1.0
    )
    result = recommend(uk_student_profile, [make_card(name="Any Card")], gbp_inr_table())

    assert sum(result.weights_used.values()) == pytest.approx(1.0)
    for component in result.recommended.scores:
        assert 0.0 <= component.weight <= 1.0


def test_identical_cards_are_reported_as_tied(uk_student_profile):
    a = make_card(name="Twin A")
    b = make_card(name="Twin B")

    result = recommend(uk_student_profile, [a, b], gbp_inr_table())

    assert result.tied_with_recommended, "cards with identical terms should be flagged as tied"
    assert result.confidence in (Confidence.MEDIUM, Confidence.LOW)


def test_unknown_atm_fee_never_makes_a_card_look_cheaper(uk_student_profile):
    """The core no-fake-data rule (BUILD.md sections 58, 83)."""
    published = make_card(name="Published", atm_fee=Decimal(500))
    silent = make_card(name="Silent", atm_fee_unknown=True)

    uk_student_profile.atm_withdrawals_per_month = 8
    result = recommend(uk_student_profile, [published, silent], gbp_inr_table())

    silent_eval = next(e for e in result.comparison if e.card.card_name == "Silent")
    published_eval = next(e for e in result.comparison if e.card.card_name == "Published")

    from app.enums import FeeType

    assert FeeType.ATM_WITHDRAWAL in silent_eval.cost.imputed_components
    assert silent_eval.cost.total_inr >= published_eval.cost.total_inr
    assert any(c.is_imputed and c.imputation_note for c in silent_eval.cost.components)


def test_inactive_and_unapplyable_cards_are_hard_filtered(uk_student_profile):
    good = make_card(name="Good Card")
    discontinued = make_card(name="Discontinued", is_active=False)
    no_route = make_card(name="No Application Route", application_url=None)

    result = recommend(uk_student_profile, [good, discontinued, no_route], gbp_inr_table())

    excluded_names = {e.card_name for e in result.excluded}
    assert excluded_names == {"Discontinued", "No Application Route"}
    assert len(result.comparison) == 1


def test_engine_is_deterministic(uk_student_profile):
    cards = [make_card(name=f"Card {i}", issuance=Decimal(i * 100)) for i in range(6)]
    fx = gbp_inr_table()

    first = recommend(uk_student_profile, cards, fx)
    second = recommend(uk_student_profile, cards, fx)

    assert [e.card.id for e in first.comparison] == [e.card.id for e in second.comparison]
    assert [e.final_score for e in first.comparison] == [e.final_score for e in second.comparison]


def test_returns_at_most_three_and_never_pads(uk_student_profile):
    many = [make_card(name=f"Card {i}", issuance=Decimal(i * 250)) for i in range(7)]
    result = recommend(uk_student_profile, many, gbp_inr_table())
    assert len(result.alternatives) == 2  # winner + 2 alternatives == top 3

    only_two = [make_card(name="Solo A"), make_card(name="Solo B", issuance=Decimal(9000))]
    small = recommend(uk_student_profile, only_two, gbp_inr_table())
    assert len(small.alternatives) == 1, "must not invent a third recommendation"


def test_match_percentage_is_a_whole_number(uk_student_profile):
    result = recommend(uk_student_profile, [make_card(name="Any")], gbp_inr_table())
    assert isinstance(result.recommended.match_percentage, int)
