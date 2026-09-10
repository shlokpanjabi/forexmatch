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


def test_zero_markup_conversion_beats_a_full_spread(uk_student_profile):
    """Converting at 0% is not the same drawback as converting at 3.5%."""
    from app.enums import ScoreComponent

    free_conversion = make_card(
        name="Zero Markup", wallet_currencies=("USD",), cross_currency_pct=Decimal("0")
    )
    full_spread = make_card(
        name="Full Spread", wallet_currencies=("USD",), cross_currency_pct=Decimal("3.5")
    )

    result = recommend(uk_student_profile, [free_conversion, full_spread], gbp_inr_table())

    zero = next(e for e in result.comparison if e.card.card_name == "Zero Markup")
    spread = next(e for e in result.comparison if e.card.card_name == "Full Spread")

    zero_score = zero.score_for(ScoreComponent.CURRENCY_SUPPORT).score
    spread_score = spread.score_for(ScoreComponent.CURRENCY_SUPPORT).score
    assert zero_score > spread_score
    explanation = zero.score_for(ScoreComponent.CURRENCY_SUPPORT).explanation
    assert "no cross-currency fee" in explanation
    # It must not read as a free conversion — the rate spread is still unknown.
    assert "spread is not published" in explanation


def test_card_with_no_currency_support_and_no_conversion_terms_is_excluded(uk_student_profile):
    """It cannot be used at the destination, so it is filtered rather than scored."""
    published = make_card(name="Published", wallet_currencies=("USD",), cross_currency_pct=Decimal("3.5"))
    silent = make_card(name="Silent", wallet_currencies=("USD",), cross_currency_pct=None)

    result = recommend(uk_student_profile, [published, silent], gbp_inr_table())

    excluded = {e.card_name: e.reason for e in result.excluded}
    assert "Silent" in excluded
    assert "cross-currency" in excluded["Silent"]
    assert [e.card.card_name for e in result.comparison] == ["Published"]


def test_unverified_currency_list_is_reported_not_asserted(uk_student_profile):
    """We must not claim a card lacks GBP when we simply never confirmed it."""
    from app.enums import ScoreComponent

    unverified = make_card(name="Unverified", wallet_currencies=())
    result = recommend(uk_student_profile, [unverified], gbp_inr_table())

    explanation = result.recommended.score_for(ScoreComponent.CURRENCY_SUPPORT).explanation
    assert "could not be verified" in explanation
    assert "does not" not in explanation.lower()


def test_a_waived_conversion_fee_is_not_a_free_conversion(uk_student_profile):
    """A provider advertising "zero cross-currency fees" has told us about their
    fee, not their rate.

    A card that does not hold the spend currency converts every purchase at the
    provider's own rate, and that spread is not published. Pricing it at zero
    would let a single-currency card look free to spend abroad — the same
    mistake as reading an unpublished fee as nil (BUILD.md sections 19, 58).
    """
    from app.enums import FeeType

    zero_fee = make_card(
        name="Zero Fee USD",
        wallet_currencies=("USD",),
        cross_currency_pct=Decimal("0"),
        issuance=Decimal(0),
        reload_fee=Decimal(0),
        atm_fee=Decimal(0),
    )
    gbp_wallet = make_card(name="Holds GBP", wallet_currencies=("GBP",), issuance=Decimal(500))
    # A card that publishes its markup supplies the worst-case baseline. A card
    # that holds GBP does not — it never converts, so its zero says nothing.
    discloses = make_card(
        name="Discloses 3.5%", wallet_currencies=("USD",), cross_currency_pct=Decimal("3.5")
    )

    result = recommend(uk_student_profile, [zero_fee, gbp_wallet, discloses], gbp_inr_table())
    converting = next(e for e in result.comparison if e.card.card_name == "Zero Fee USD")

    # The conversion is costed, not free.
    assert converting.cost.total_inr > 0
    assert FeeType.CROSS_CURRENCY in converting.cost.imputed_components
    note = next(
        c.imputation_note for c in converting.cost.components if c.fee_type is FeeType.CROSS_CURRENCY
    )
    assert note and "spread is not published" in note

    # And the user is told why.
    assert any("does not hold GBP" in a and "spread" in a for a in converting.cost.assumptions)


def test_holding_the_currency_really_is_free_to_convert(uk_student_profile):
    """The counterpart: no conversion happens, so nothing is imputed."""
    from app.enums import FeeType

    gbp_wallet = make_card(name="Holds GBP", wallet_currencies=("GBP",))
    result = recommend(uk_student_profile, [gbp_wallet], gbp_inr_table())

    cross = next(
        c for c in result.recommended.cost.components if c.fee_type is FeeType.CROSS_CURRENCY
    )
    assert cross.amount_inr == 0
    assert not cross.is_imputed
