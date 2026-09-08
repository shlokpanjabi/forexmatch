#!/usr/bin/env python
"""Load the sourced card catalogue into PostgreSQL.

Run with:  python scripts/seed_cards.py [--dry-run]

The loader enforces the rule that makes this catalogue trustworthy: every fee,
limit, benefit, currency and eligibility row must name a source declared on its
card, and that source must be a real URL with a verification date. A file that
breaks the rule aborts the load rather than inserting a partially-sourced card
(BUILD.md sections 62, 63, 83).

Re-running is safe: a card is matched by slug and its facts are rebuilt, so the
JSON files remain the single definition of the catalogue.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.db.models import (  # noqa: E402
    Card,
    CardBenefit,
    CardCurrency,
    CardEligibility,
    CardFee,
    CardLimit,
    Source,
)
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.enums import (  # noqa: E402
    BenefitType,
    CardNetwork,
    CardType,
    EligibilityCriterion,
    FeeType,
    LimitType,
    SourceType,
)

DATA_DIR = BACKEND_ROOT / "data" / "cards"


class SeedError(RuntimeError):
    """A seed file violates the catalogue's data rules."""


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _decimal(value: str | int | float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _validate_card(card: dict, file: Path) -> None:
    where = f"{file.name}:{card.get('slug', '<no slug>')}"

    for field in ("slug", "card_name", "card_type"):
        if not card.get(field):
            raise SeedError(f"{where}: missing required field '{field}'")

    sources = card.get("sources") or []
    if not sources:
        raise SeedError(f"{where}: a card must declare at least one source")

    keys: set[str] = set()
    for source in sources:
        for field in ("key", "url", "domain", "source_type", "retrieved_at", "last_verified_at"):
            if not source.get(field):
                raise SeedError(f"{where}: source is missing '{field}'")
        parsed = urlparse(source["url"])
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise SeedError(f"{where}: source URL is not a valid absolute URL: {source['url']}")
        keys.add(source["key"])

    # Every fact must point at a declared source.
    for collection in ("currencies", "fees", "limits", "benefits", "eligibility"):
        for fact in card.get(collection) or []:
            key = fact.get("source")
            if not key:
                raise SeedError(f"{where}: a {collection[:-1]} entry has no 'source' key")
            if key not in keys:
                raise SeedError(f"{where}: {collection} references undeclared source '{key}'")

    for fee in card.get("fees") or []:
        amount = fee.get("amount")
        percentage = fee.get("percentage")
        if amount is None and percentage is None and not (fee.get("is_unknown") or fee.get("is_waived")):
            raise SeedError(
                f"{where}: fee '{fee.get('fee_type')}' has no amount, no percentage and is not "
                "marked unknown or waived. An unpriced fee must be explicit, never implied zero."
            )
        if amount is not None and Decimal(str(amount)) < 0:
            raise SeedError(f"{where}: negative fee amount for '{fee.get('fee_type')}'")
        if percentage is not None and not (0 <= Decimal(str(percentage)) <= 100):
            raise SeedError(f"{where}: percentage out of range for '{fee.get('fee_type')}'")
        if amount is not None and not fee.get("currency"):
            raise SeedError(f"{where}: fee '{fee.get('fee_type')}' has an amount but no currency")

    if card.get("application_url"):
        parsed = urlparse(card["application_url"])
        if parsed.scheme not in ("http", "https"):
            raise SeedError(f"{where}: application_url is not a valid absolute URL")


def load_files() -> list[tuple[Path, dict]]:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise SeedError(f"no seed files found in {DATA_DIR}")
    loaded = []
    slugs: dict[str, Path] = {}
    for file in files:
        payload = json.loads(file.read_text())
        provider = payload.get("provider")
        if not provider:
            raise SeedError(f"{file.name}: missing 'provider'")
        for card in payload.get("cards") or []:
            _validate_card(card, file)
            slug = card["slug"]
            if slug in slugs:
                raise SeedError(f"duplicate card slug '{slug}' in {file.name} and {slugs[slug].name}")
            slugs[slug] = file
        loaded.append((file, payload))
    return loaded


async def seed(dry_run: bool = False) -> None:
    loaded = load_files()
    total_cards = sum(len(p.get("cards") or []) for _, p in loaded)
    print(f"Validated {total_cards} cards across {len(loaded)} provider files.")
    if dry_run:
        print("Dry run — nothing written.")
        return

    inserted = updated = 0
    facts = 0

    async with session_scope() as session:
        for _file, payload in loaded:
            provider = payload["provider"]
            for entry in payload["cards"]:
                existing = (
                    await session.execute(select(Card).where(Card.slug == entry["slug"]))
                ).scalar_one_or_none()

                if existing is None:
                    card = Card(slug=entry["slug"])
                    session.add(card)
                    inserted += 1
                else:
                    card = existing
                    updated += 1
                    # Rebuild facts so the JSON stays authoritative. Sources are
                    # deleted last because the facts reference them.
                    for model in (CardFee, CardLimit, CardBenefit, CardEligibility, CardCurrency):
                        await session.execute(delete(model).where(model.card_id == card.id))
                    await session.flush()
                    await session.execute(delete(Source).where(Source.card_id == card.id))
                    await session.flush()

                card.provider = provider
                card.card_name = entry["card_name"]
                card.card_type = CardType(entry["card_type"])
                card.network = CardNetwork(entry.get("network") or "unknown")
                card.description = entry.get("description")
                card.is_active = entry.get("is_active", True)
                card.application_url = entry.get("application_url")
                card.affiliate_url = entry.get("affiliate_url")
                card.affiliate_provider = entry.get("affiliate_provider")
                card.affiliate_tracking_enabled = entry.get("affiliate_tracking_enabled", False)
                await session.flush()

                by_key: dict[str, Source] = {}
                latest_verified: datetime | None = None
                for spec in entry["sources"]:
                    verified = _parse_date(spec["last_verified_at"])
                    source = Source(
                        card_id=card.id,
                        url=spec["url"],
                        domain=spec["domain"],
                        title=spec.get("title"),
                        source_type=SourceType(spec["source_type"]),
                        retrieved_at=_parse_date(spec["retrieved_at"]),
                        last_verified_at=verified,
                        notes=spec.get("notes"),
                    )
                    session.add(source)
                    by_key[spec["key"]] = source
                    latest_verified = verified if latest_verified is None else max(latest_verified, verified)
                await session.flush()

                card.last_verified_at = latest_verified

                for spec in entry.get("currencies") or []:
                    session.add(
                        CardCurrency(
                            card_id=card.id,
                            currency_code=spec["code"].upper(),
                            supported=spec.get("supported", True),
                            direct_wallet=spec.get("direct_wallet", True),
                            source_id=by_key[spec["source"]].id,
                        )
                    )
                    facts += 1

                for spec in entry.get("fees") or []:
                    session.add(
                        CardFee(
                            card_id=card.id,
                            fee_type=FeeType(spec["fee_type"]),
                            amount=_decimal(spec.get("amount")),
                            currency=(spec.get("currency") or None),
                            percentage=_decimal(spec.get("percentage")),
                            min_amount=_decimal(spec.get("min_amount")),
                            max_amount=_decimal(spec.get("max_amount")),
                            is_unknown=spec.get("is_unknown", False),
                            is_waived=spec.get("is_waived", False),
                            conditions=spec.get("conditions"),
                            source_id=by_key[spec["source"]].id,
                        )
                    )
                    facts += 1

                for spec in entry.get("limits") or []:
                    session.add(
                        CardLimit(
                            card_id=card.id,
                            limit_type=LimitType(spec["limit_type"]),
                            amount=_decimal(spec.get("amount")),
                            currency=(spec.get("currency") or None),
                            period=spec.get("period"),
                            conditions=spec.get("conditions"),
                            source_id=by_key[spec["source"]].id,
                        )
                    )
                    facts += 1

                for spec in entry.get("benefits") or []:
                    session.add(
                        CardBenefit(
                            card_id=card.id,
                            benefit_type=BenefitType(spec["benefit_type"]),
                            description=spec["description"],
                            value=spec.get("value"),
                            conditions=spec.get("conditions"),
                            source_id=by_key[spec["source"]].id,
                        )
                    )
                    facts += 1

                for spec in entry.get("eligibility") or []:
                    session.add(
                        CardEligibility(
                            card_id=card.id,
                            criterion=EligibilityCriterion(spec["criterion"]),
                            value=spec.get("value"),
                            description=spec["description"],
                            source_id=by_key[spec["source"]].id,
                        )
                    )
                    facts += 1

                await session.flush()

    print(f"Seeded {inserted} new and {updated} existing cards, {facts} sourced facts.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the ForexMatch card catalogue.")
    parser.add_argument("--dry-run", action="store_true", help="validate the files without writing")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.dry_run))
    except SeedError as exc:
        print(f"Seed aborted: {exc}", file=sys.stderr)
        return 1
    return 0


async def _run(dry_run: bool) -> None:
    try:
        await seed(dry_run)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
