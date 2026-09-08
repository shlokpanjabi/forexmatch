"""Verification pipeline (BUILD.md sections 42–44, 84).

Compares stored card facts against the provider's current published
information and records *proposed* changes. Nothing here writes to the card
catalogue: a human approves each change, so an automated misreading can never
silently alter a fee a student will act on.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Card, VerificationChange, VerificationRun
from app.enums import Confidence, VerificationRunStatus, VerificationStatus
from app.recommendation.models import classify_freshness
from app.recommendation.service import to_card_facts
from app.research.service import ResearchService

logger = structlog.get_logger(__name__)

#: Facts worth re-checking, in the order a reviewer cares about them.
VERIFIED_TOPICS: tuple[str, ...] = (
    "issuance fee",
    "reload fee",
    "ATM withdrawal fee",
    "cross currency markup",
    "supported currencies",
)


class VerificationService:
    def __init__(self, session: AsyncSession, research: ResearchService | None = None) -> None:
        self._session = session
        self._research = research or ResearchService()

    async def verify_card(
        self, card_id: uuid.UUID, *, triggered_by: str = "manual"
    ) -> VerificationRun:
        card = (await self._session.execute(select(Card).where(Card.id == card_id))).scalar_one_or_none()
        if card is None:
            raise ValueError(f"no card with id {card_id}")

        run = VerificationRun(
            card_id=card.id,
            status=VerificationRunStatus.RUNNING,
            triggered_by=triggered_by,
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()

        facts = to_card_facts(card)
        checked = 0
        proposed = 0

        try:
            for topic in VERIFIED_TOPICS:
                result = await self._research.search(card.provider, card.card_name, topic)
                if result.status != "ok":
                    logger.info("verification.research_unavailable", card=card.slug, topic=topic)
                    continue
                checked += len(result.findings)

                # Record the retrieved evidence as a proposed change for review.
                # Extraction is deliberately conservative: we surface what the
                # source says and let a human decide, rather than parsing a
                # figure out of prose and trusting it.
                for finding in result.findings:
                    if not finding.is_official:
                        continue
                    self._session.add(
                        VerificationChange(
                            run_id=run.id,
                            card_id=card.id,
                            field=f"research.{topic.replace(' ', '_')}",
                            old_value=_summarise_current(facts, topic),
                            new_value=finding.snippet[:2000],
                            source_id=None,
                            confidence=Confidence.LOW,
                            status=VerificationStatus.PENDING,
                            reviewer_note=f"Retrieved from {finding.url}",
                        )
                    )
                    proposed += 1

            run.status = VerificationRunStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001
            logger.exception("verification.failed", card=card.slug)
            run.status = VerificationRunStatus.FAILED
            run.error_message = str(exc)[:500]

        run.sources_checked = checked
        run.changes_proposed = proposed
        run.completed_at = datetime.now(UTC)
        await self._session.flush()
        return run

    async def stale_cards(self, *, days: int = 90) -> list[Card]:
        """Cards whose data is old enough to be worth re-checking."""
        rows = (await self._session.execute(select(Card).where(Card.is_active.is_(True)))).scalars().unique().all()
        return [
            card
            for card in rows
            if classify_freshness(card.last_verified_at).value in ("aging", "stale", "unknown")
        ]

    async def decide(
        self, change_id: uuid.UUID, *, approve: bool, note: str | None = None
    ) -> VerificationChange:
        change = (
            await self._session.execute(select(VerificationChange).where(VerificationChange.id == change_id))
        ).scalar_one_or_none()
        if change is None:
            raise ValueError(f"no verification change with id {change_id}")
        change.status = VerificationStatus.APPROVED if approve else VerificationStatus.REJECTED
        if note:
            change.reviewer_note = note
        await self._session.flush()
        return change


def _summarise_current(facts, topic: str) -> str | None:
    """What the catalogue currently holds for a topic, for side-by-side review."""
    from app.enums import FeeType

    mapping = {
        "issuance fee": FeeType.ISSUANCE,
        "reload fee": FeeType.RELOAD,
        "ATM withdrawal fee": FeeType.ATM_WITHDRAWAL,
        "cross currency markup": FeeType.CROSS_CURRENCY,
    }
    if topic == "supported currencies":
        return ", ".join(facts.supported_currency_codes) or "not verified"
    fee_type = mapping.get(topic)
    if fee_type is None:
        return None
    fee = facts.fee(fee_type)
    if fee is None:
        return "no record"
    if fee.is_unknown:
        return "unknown (provider publishes no figure)"
    if fee.is_waived:
        return "waived"
    parts = []
    if fee.amount is not None:
        parts.append(f"{fee.currency or ''} {fee.amount}".strip())
    if fee.percentage is not None:
        parts.append(f"{fee.percentage}%")
    return " + ".join(parts) or None
