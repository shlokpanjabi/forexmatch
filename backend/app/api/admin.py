"""Internal endpoints, guarded by a shared secret (BUILD.md section 44)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import AdminGuard, DbSession
from app.db.models import Card, VerificationChange, VerificationRun
from app.enums import VerificationStatus
from app.errors import NotFoundError
from app.recommendation.service import to_card_facts
from app.schemas.serializers import card_detail, card_summary
from app.verification import VerificationService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cards")
async def admin_list_cards(db: DbSession, _: AdminGuard) -> dict[str, Any]:
    rows = (await db.execute(select(Card).order_by(Card.provider, Card.card_name))).scalars().unique().all()
    cards = [to_card_facts(r) for r in rows]
    return {
        "count": len(cards),
        "cards": [
            card_summary(c)
            | {
                "is_active": c.is_active,
                "fee_count": len(c.fees),
                "source_count": len(c.sources),
                "unknown_fee_count": sum(1 for f in c.fees if f.is_unknown),
            }
            for c in cards
        ],
    }


@router.get("/cards/{card_id}")
async def admin_get_card(card_id: uuid.UUID, db: DbSession, _: AdminGuard) -> dict[str, Any]:
    row = (await db.execute(select(Card).where(Card.id == card_id))).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"No card with id {card_id}.")
    return card_detail(to_card_facts(row))


@router.post("/cards/{card_id}/verify")
async def admin_verify_card(card_id: uuid.UUID, db: DbSession, _: AdminGuard) -> dict[str, Any]:
    try:
        run = await VerificationService(db).verify_card(card_id)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "sources_checked": run.sources_checked,
        "changes_proposed": run.changes_proposed,
        "error_message": run.error_message,
        "note": "Proposed changes are pending review; nothing has been written to the catalogue.",
    }


@router.get("/verification/changes")
async def admin_list_changes(
    db: DbSession, _: AdminGuard, status: str = "pending"
) -> dict[str, Any]:
    stmt = select(VerificationChange).order_by(VerificationChange.created_at.desc()).limit(200)
    if status != "all":
        stmt = stmt.where(VerificationChange.status == VerificationStatus(status))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "changes": [
            {
                "id": str(c.id),
                "card_id": str(c.card_id),
                "field": c.field,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "confidence": c.confidence.value,
                "status": c.status.value,
                "reviewer_note": c.reviewer_note,
                "created_at": c.created_at.isoformat(),
            }
            for c in rows
        ],
    }


class DecisionRequest(BaseModel):
    note: str | None = None


@router.post("/verification/changes/{change_id}/approve")
async def admin_approve(
    change_id: uuid.UUID, request: DecisionRequest, db: DbSession, _: AdminGuard
) -> dict[str, Any]:
    try:
        change = await VerificationService(db).decide(change_id, approve=True, note=request.note)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    return {"id": str(change.id), "status": change.status.value}


@router.post("/verification/changes/{change_id}/reject")
async def admin_reject(
    change_id: uuid.UUID, request: DecisionRequest, db: DbSession, _: AdminGuard
) -> dict[str, Any]:
    try:
        change = await VerificationService(db).decide(change_id, approve=False, note=request.note)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    return {"id": str(change.id), "status": change.status.value}


@router.get("/verification/runs")
async def admin_list_runs(db: DbSession, _: AdminGuard) -> dict[str, Any]:
    rows = (
        (await db.execute(select(VerificationRun).order_by(VerificationRun.started_at.desc()).limit(50)))
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "runs": [
            {
                "id": str(r.id),
                "card_id": str(r.card_id),
                "status": r.status.value,
                "sources_checked": r.sources_checked,
                "changes_proposed": r.changes_proposed,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ],
    }


@router.get("/stale-cards")
async def admin_stale_cards(db: DbSession, _: AdminGuard) -> dict[str, Any]:
    cards = await VerificationService(db).stale_cards()
    return {
        "count": len(cards),
        "cards": [
            {
                "id": str(c.id),
                "slug": c.slug,
                "provider": c.provider,
                "card_name": c.card_name,
                "last_verified_at": c.last_verified_at.isoformat() if c.last_verified_at else None,
            }
            for c in cards
        ],
    }
