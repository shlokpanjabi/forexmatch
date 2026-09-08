"""Catalogue quality gates (BUILD.md section 63).

These run against the real seed files, so a bad edit to the catalogue fails the
build rather than reaching the database.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.enums import BenefitType, EligibilityCriterion, FeeType, LimitType, SourceType

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cards"
FACT_COLLECTIONS = ("currencies", "fees", "limits", "benefits", "eligibility")


def all_cards() -> list[tuple[str, dict]]:
    cards = []
    for file in sorted(DATA_DIR.glob("*.json")):
        payload = json.loads(file.read_text())
        for card in payload["cards"]:
            cards.append((f"{file.name}:{card['slug']}", card))
    return cards


CARDS = all_cards()
IDS = [name for name, _ in CARDS]


def test_catalogue_is_not_empty():
    assert len(CARDS) >= 10, "the catalogue should carry a meaningful set of real products"


def test_slugs_are_unique():
    slugs = [card["slug"] for _, card in CARDS]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_active_card_has_an_application_route(name, card):
    if card.get("is_active", True) and not card.get("application_url"):
        # Permitted only when the card documents why it cannot be applied for.
        reasons = [e["criterion"] for e in card.get("eligibility") or []]
        assert "existing_relationship" in reasons, (
            f"{name}: an active card needs an application URL, or eligibility explaining its absence"
        )


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_every_fact_names_a_declared_source(name, card):
    keys = {s["key"] for s in card["sources"]}
    for collection in FACT_COLLECTIONS:
        for fact in card.get(collection) or []:
            assert fact.get("source"), f"{name}: {collection} entry has no source"
            assert fact["source"] in keys, f"{name}: {collection} names undeclared source"


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_sources_are_valid_and_dated(name, card):
    assert card["sources"], f"{name}: no sources"
    for source in card["sources"]:
        parsed = urlparse(source["url"])
        assert parsed.scheme in ("http", "https"), f"{name}: bad source scheme"
        assert parsed.netloc, f"{name}: source URL has no host"
        assert source.get("last_verified_at"), f"{name}: source missing last_verified_at"
        assert source.get("retrieved_at"), f"{name}: source missing retrieved_at"
        SourceType(source["source_type"])


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_fees_are_valid(name, card):
    for fee in card.get("fees") or []:
        FeeType(fee["fee_type"])
        amount = fee.get("amount")
        percentage = fee.get("percentage")

        assert amount is not None or percentage is not None or fee.get("is_unknown") or fee.get("is_waived"), (
            f"{name}: fee '{fee['fee_type']}' is neither priced nor explicitly unknown/waived"
        )
        if amount is not None:
            assert Decimal(str(amount)) >= 0, f"{name}: negative fee"
            assert fee.get("currency"), f"{name}: fee has an amount but no currency"
            assert len(fee["currency"]) == 3, f"{name}: fee currency is not an ISO code"
        if percentage is not None:
            assert Decimal("0") <= Decimal(str(percentage)) <= Decimal("100"), f"{name}: bad percentage"


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_unknown_fee_is_never_also_priced(name, card):
    """The whole point of is_unknown is that it is not a number."""
    for fee in card.get("fees") or []:
        if fee.get("is_unknown"):
            assert fee.get("amount") is None and fee.get("percentage") is None, (
                f"{name}: fee '{fee['fee_type']}' is marked unknown but carries a value"
            )
            assert not fee.get("is_waived"), f"{name}: fee cannot be both unknown and waived"


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_currency_codes_are_iso_and_unique(name, card):
    seen = set()
    for entry in card.get("currencies") or []:
        code = entry["code"]
        assert len(code) == 3 and code.isalpha() and code.isupper(), f"{name}: bad currency {code}"
        assert code not in seen, f"{name}: duplicate currency {code}"
        seen.add(code)


@pytest.mark.parametrize("name,card", CARDS, ids=IDS)
def test_enums_are_valid(name, card):
    for entry in card.get("limits") or []:
        LimitType(entry["limit_type"])
    for entry in card.get("benefits") or []:
        BenefitType(entry["benefit_type"])
        assert entry.get("description"), f"{name}: benefit needs a description"
    for entry in card.get("eligibility") or []:
        EligibilityCriterion(entry["criterion"])
        assert entry.get("description"), f"{name}: eligibility needs a description"


def test_no_card_claims_a_zero_fee_without_saying_so():
    """A ₹0 fee must be an explicit is_waived claim, not an incidental zero."""
    for name, card in CARDS:
        for fee in card.get("fees") or []:
            amount = fee.get("amount")
            if amount is not None and Decimal(str(amount)) == 0:
                assert fee.get("is_waived"), (
                    f"{name}: fee '{fee['fee_type']}' is zero but not marked is_waived — "
                    "a zero charge must be a published claim, not an assumption"
                )
